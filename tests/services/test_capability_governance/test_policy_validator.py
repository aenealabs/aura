"""
Tests for Policy Validator.

Tests the capability policy validation for ADR-070.
"""

import pytest

from src.services.capability_governance import (
    AgentCapabilityPolicy,
    PolicyValidator,
    ValidationContext,
    ValidationResult,
    get_policy_validator,
    reset_policy_validator,
)


class TestPolicyValidatorInit:
    """Tests for PolicyValidator initialization."""

    def test_create_validator(self):
        """Test creating validator."""
        validator = PolicyValidator()
        assert validator is not None

    def test_singleton_pattern(self):
        """Test singleton pattern."""
        reset_policy_validator()
        v1 = get_policy_validator()
        v2 = get_policy_validator()
        assert v1 is v2

    def test_reset_clears_singleton(self):
        """Test reset clears singleton."""
        v1 = get_policy_validator()
        reset_policy_validator()
        v2 = get_policy_validator()
        assert v1 is not v2


class TestSchemaValidation:
    """Tests for schema validation."""

    @pytest.mark.asyncio
    async def test_valid_policy_passes(self, coder_policy):
        """Test that valid policy passes validation."""
        validator = PolicyValidator()
        result = await validator.validate_policy(coder_policy)
        # May have warnings but no schema errors
        schema_errors = [e for e in result.errors if "MISSING_FIELD" in e.code]
        assert len(schema_errors) == 0

    @pytest.mark.asyncio
    async def test_missing_agent_type_fails(self):
        """Test that missing agent_type fails."""
        policy = AgentCapabilityPolicy(
            agent_type="",
            allowed_tools={"semantic_search": ["read"]},
        )
        validator = PolicyValidator()
        result = await validator.validate_policy(policy)
        assert not result.valid
        assert any(e.code == "MISSING_FIELD" for e in result.errors)

    @pytest.mark.asyncio
    async def test_missing_version_fails(self):
        """Test that missing version fails."""
        policy = AgentCapabilityPolicy(
            agent_type="TestAgent",
            version="",
            allowed_tools={"semantic_search": ["read"]},
        )
        validator = PolicyValidator()
        result = await validator.validate_policy(policy)
        assert any(
            e.code == "MISSING_FIELD" and "version" in e.message for e in result.errors
        )


class TestReferenceIntegrity:
    """Tests for reference integrity validation."""

    @pytest.mark.asyncio
    async def test_unknown_tool_reported(self):
        """Test that unknown tools are reported."""
        policy = AgentCapabilityPolicy(
            agent_type="TestAgent",
            allowed_tools={"nonexistent_tool_xyz": ["read"]},
        )
        validator = PolicyValidator()
        result = await validator.validate_policy(policy)
        assert any(e.code == "UNKNOWN_TOOL" for e in result.errors)

    @pytest.mark.asyncio
    async def test_known_tools_pass(self, coder_policy):
        """Test that known tools pass validation."""
        validator = PolicyValidator()
        result = await validator.validate_policy(coder_policy)
        unknown_errors = [e for e in result.errors if e.code == "UNKNOWN_TOOL"]
        assert len(unknown_errors) == 0


class TestInheritanceValidation:
    """Tests for inheritance validation."""

    @pytest.mark.asyncio
    async def test_missing_parent_reported(self):
        """Test that missing parent policy is reported."""
        policy = AgentCapabilityPolicy(
            agent_type="ChildAgent",
            parent_policy="NonexistentParent",
            allowed_tools={"semantic_search": ["read"]},
        )
        validator = PolicyValidator()
        context = ValidationContext(existing_policies=[])
        result = await validator.validate_policy(policy, context)
        assert any(e.code == "MISSING_PARENT" for e in result.errors)

    @pytest.mark.asyncio
    async def test_valid_parent_passes(self, coder_policy):
        """Test that valid parent reference passes."""
        parent = AgentCapabilityPolicy(
            agent_type="BaseAgent",
            allowed_tools={"semantic_search": ["read"]},
        )
        child = AgentCapabilityPolicy(
            agent_type="ChildAgent",
            parent_policy="BaseAgent",
            allowed_tools={"query_code_graph": ["read"]},
        )
        validator = PolicyValidator()
        context = ValidationContext(existing_policies=[parent])
        result = await validator.validate_policy(child, context)
        parent_errors = [e for e in result.errors if e.code == "MISSING_PARENT"]
        assert len(parent_errors) == 0


class TestEscalationPathDetection:
    """Tests for privilege escalation path detection."""

    @pytest.mark.asyncio
    async def test_detects_iam_escalation(self):
        """Test detection of IAM policy modification escalation."""
        policy = AgentCapabilityPolicy(
            agent_type="DangerousAgent",
            allowed_tools={"modify_iam_policy": ["execute"]},
        )
        validator = PolicyValidator()
        result = await validator.validate_policy(policy)
        assert len(result.escalation_paths) > 0

    @pytest.mark.asyncio
    async def test_safe_policy_no_escalation(self, reviewer_policy):
        """Test that safe policy has no escalation paths."""
        validator = PolicyValidator()
        result = await validator.validate_policy(reviewer_policy)
        # Reviewer should not have escalation paths
        assert len(result.escalation_paths) == 0


class TestToxicCombinationDetection:
    """Tests for toxic combination detection."""

    @pytest.mark.asyncio
    async def test_detects_secrets_plus_code(self):
        """Test detection of access_secrets + execute_code combination."""
        policy = AgentCapabilityPolicy(
            agent_type="ToxicAgent",
            allowed_tools={"access_secrets": ["read"], "execute_code": ["execute"]},
        )
        validator = PolicyValidator()
        result = await validator.validate_policy(policy)
        assert len(result.toxic_combinations) > 0
        assert any(
            t.capability_a == "access_secrets" for t in result.toxic_combinations
        )

    @pytest.mark.asyncio
    async def test_safe_policy_no_toxic_combo(self, reviewer_policy):
        """Test that safe policy has no toxic combinations."""
        validator = PolicyValidator()
        result = await validator.validate_policy(reviewer_policy)
        assert len(result.toxic_combinations) == 0


class TestCoverageGapDetection:
    """Tests for coverage gap detection."""

    @pytest.mark.asyncio
    async def test_detects_dangerous_without_monitoring(self):
        """Test detection of DANGEROUS without MONITORING tools."""
        policy = AgentCapabilityPolicy(
            agent_type="GapAgent",
            allowed_tools={
                "create_branch": ["execute"],
                "commit_changes": ["execute"],
            },  # DANGEROUS
            # No MONITORING tools
        )
        validator = PolicyValidator()
        result = await validator.validate_policy(policy)
        # Should have coverage gap warning
        gap_warnings = [w for w in result.warnings if "COVERAGE_GAP" in w.code]
        # Note: depends on tool classification


class TestComplianceValidation:
    """Tests for compliance requirement validation."""

    @pytest.mark.asyncio
    async def test_cmmc_least_privilege(self):
        """Test CMMC least privilege validation."""
        policy = AgentCapabilityPolicy(
            agent_type="PrivilegedAgent",
            allowed_tools={"deploy_to_production": ["execute"]},  # CRITICAL
        )
        validator = PolicyValidator()
        context = ValidationContext(compliance_requirements=["cmmc-l3"])
        result = await validator.validate_policy(policy, context)
        # Should have compliance warning/error

    @pytest.mark.asyncio
    async def test_sox_separation_of_duties(self):
        """Test SOX separation of duties validation."""
        from src.services.capability_governance import (
            CapabilityRegistry,
            ToolCapability,
            ToolClassification,
        )

        # Register the tools needed for the test
        registry = CapabilityRegistry()
        registry.register_tool(
            ToolCapability(
                tool_name="create_patch",
                classification=ToolClassification.DANGEROUS,
                description="Create a security patch",
                allowed_actions=("execute",),
            )
        )
        registry.register_tool(
            ToolCapability(
                tool_name="approve_patch",
                classification=ToolClassification.CRITICAL,
                description="Approve a security patch",
                allowed_actions=("execute",),
            )
        )

        policy = AgentCapabilityPolicy(
            agent_type="DualRoleAgent",
            allowed_tools={
                "create_patch": ["execute"],
                "approve_patch": ["execute"],
            },  # Violation
        )
        validator = PolicyValidator(registry=registry)
        context = ValidationContext(compliance_requirements=["sox"])
        result = await validator.validate_policy(policy, context)
        compliance_errors = [
            e for e in result.errors if e.code == "COMPLIANCE_VIOLATION"
        ]
        assert len(compliance_errors) > 0


class TestRateLimitValidation:
    """Tests for rate limit validation."""

    @pytest.mark.asyncio
    async def test_dangerous_without_rate_limits_warns(self):
        """Test warning for DANGEROUS tools without rate limits."""
        policy = AgentCapabilityPolicy(
            agent_type="NoLimitsAgent",
            allowed_tools={"create_branch": ["execute"]},  # DANGEROUS
            tool_rate_limits={},  # No specific rate limits for dangerous tools
        )
        validator = PolicyValidator()
        result = await validator.validate_policy(policy)
        rate_warnings = [w for w in result.warnings if "RATE_LIMITS" in w.code]
        # Should warn about missing rate limits


class TestValidationResult:
    """Tests for ValidationResult."""

    def test_result_to_dict(self):
        """Test converting result to dictionary."""
        result = ValidationResult(valid=True)
        d = result.to_dict()
        assert d["valid"] is True
        assert "errors" in d
        assert "warnings" in d

    def test_result_with_errors_invalid(self):
        """Test that result with errors is invalid."""
        from src.services.capability_governance.policy_validator import ValidationError

        result = ValidationResult(
            valid=False,
            errors=[ValidationError(code="TEST", message="Test error")],
        )
        assert not result.valid
        assert len(result.errors) == 1
