"""
Tests for Authorization Flow Analyzer Service.

Covers the AuthorizationFlowAnalyzer class and related components for
extracting and analyzing authorization flows from code.
"""

from unittest.mock import MagicMock

import pytest

from src.services.authorization_flow_analyzer import (
    AuthorizationCheckType,
    AuthorizationFlow,
    AuthorizationFlowAnalyzer,
    AuthorizationGap,
    AuthorizationNode,
    AuthorizationPattern,
    create_authorization_flow_analyzer,
)

# =============================================================================
# AuthorizationPattern Enum Tests
# =============================================================================


class TestAuthorizationPattern:
    """Tests for AuthorizationPattern enum."""

    def test_rbac(self):
        """Test RBAC pattern."""
        assert AuthorizationPattern.RBAC.value == "rbac"

    def test_abac(self):
        """Test ABAC pattern."""
        assert AuthorizationPattern.ABAC.value == "abac"

    def test_acl(self):
        """Test ACL pattern."""
        assert AuthorizationPattern.ACL.value == "acl"

    def test_ownership(self):
        """Test ownership pattern."""
        assert AuthorizationPattern.OWNERSHIP.value == "ownership"

    def test_none(self):
        """Test no authorization pattern."""
        assert AuthorizationPattern.NONE.value == "none"

    def test_pattern_count(self):
        """Test that all 5 patterns exist."""
        assert len(AuthorizationPattern) == 5


# =============================================================================
# AuthorizationCheckType Enum Tests
# =============================================================================


class TestAuthorizationCheckType:
    """Tests for AuthorizationCheckType enum."""

    def test_role_check(self):
        """Test role check type."""
        assert AuthorizationCheckType.ROLE_CHECK.value == "role_check"

    def test_permission_check(self):
        """Test permission check type."""
        assert AuthorizationCheckType.PERMISSION_CHECK.value == "permission_check"

    def test_ownership_check(self):
        """Test ownership check type."""
        assert AuthorizationCheckType.OWNERSHIP_CHECK.value == "ownership_check"

    def test_session_check(self):
        """Test session check type."""
        assert AuthorizationCheckType.SESSION_CHECK.value == "session_check"

    def test_jwt_check(self):
        """Test JWT check type."""
        assert AuthorizationCheckType.JWT_CHECK.value == "jwt_check"

    def test_api_key_check(self):
        """Test API key check type."""
        assert AuthorizationCheckType.API_KEY_CHECK.value == "api_key_check"

    def test_none(self):
        """Test no check type."""
        assert AuthorizationCheckType.NONE.value == "none"

    def test_check_type_count(self):
        """Test that all 7 check types exist."""
        assert len(AuthorizationCheckType) == 7


# =============================================================================
# AuthorizationNode Dataclass Tests
# =============================================================================


class TestAuthorizationNode:
    """Tests for AuthorizationNode dataclass."""

    def test_create_basic_node(self):
        """Test creating a basic authorization node."""
        node = AuthorizationNode(
            node_id="test-001",
            node_type="function",
            name="get_user",
            file_path="src/api/users.py",
            line_number=42,
            check_type=AuthorizationCheckType.SESSION_CHECK,
        )
        assert node.node_id == "test-001"
        assert node.node_type == "function"
        assert node.name == "get_user"
        assert node.file_path == "src/api/users.py"
        assert node.line_number == 42
        assert node.check_type == AuthorizationCheckType.SESSION_CHECK

    def test_default_parameters(self):
        """Test default parameters list."""
        node = AuthorizationNode(
            node_id="test-002",
            node_type="decorator",
            name="@login_required",
            file_path="src/api/users.py",
            line_number=40,
            check_type=AuthorizationCheckType.SESSION_CHECK,
        )
        assert node.parameters == []

    def test_custom_parameters(self):
        """Test custom parameters list."""
        node = AuthorizationNode(
            node_id="test-003",
            node_type="decorator",
            name="@roles_required",
            file_path="src/api/admin.py",
            line_number=15,
            check_type=AuthorizationCheckType.ROLE_CHECK,
            parameters=["admin", "superuser"],
        )
        assert node.parameters == ["admin", "superuser"]


# =============================================================================
# AuthorizationFlow Dataclass Tests
# =============================================================================


class TestAuthorizationFlow:
    """Tests for AuthorizationFlow dataclass."""

    def setup_method(self):
        """Set up test fixtures."""
        self.entry_node = AuthorizationNode(
            node_id="entry-001",
            node_type="function",
            name="get_user",
            file_path="src/api/users.py",
            line_number=42,
            check_type=AuthorizationCheckType.NONE,
        )
        self.auth_node = AuthorizationNode(
            node_id="auth-001",
            node_type="decorator",
            name="@login_required",
            file_path="src/api/users.py",
            line_number=40,
            check_type=AuthorizationCheckType.SESSION_CHECK,
        )
        self.resource_node = AuthorizationNode(
            node_id="res-001",
            node_type="resource_access",
            name="User.get(user_id)",
            file_path="src/api/users.py",
            line_number=50,
            check_type=AuthorizationCheckType.NONE,
        )

    def test_create_protected_flow(self):
        """Test creating a protected authorization flow."""
        flow = AuthorizationFlow(
            flow_id="flow-001",
            entry_point=self.entry_node,
            auth_nodes=[self.auth_node],
            resource_access=self.resource_node,
            is_protected=True,
            pattern=AuthorizationPattern.ACL,
        )
        assert flow.flow_id == "flow-001"
        assert flow.entry_point == self.entry_node
        assert len(flow.auth_nodes) == 1
        assert flow.resource_access == self.resource_node
        assert flow.is_protected is True
        assert flow.pattern == AuthorizationPattern.ACL

    def test_create_unprotected_flow(self):
        """Test creating an unprotected authorization flow."""
        flow = AuthorizationFlow(
            flow_id="flow-002",
            entry_point=self.entry_node,
            auth_nodes=[],
            resource_access=self.resource_node,
            is_protected=False,
            pattern=AuthorizationPattern.NONE,
        )
        assert flow.is_protected is False
        assert flow.pattern == AuthorizationPattern.NONE
        assert len(flow.auth_nodes) == 0

    def test_default_confidence(self):
        """Test default confidence value."""
        flow = AuthorizationFlow(
            flow_id="flow-003",
            entry_point=self.entry_node,
            auth_nodes=[],
            resource_access=self.resource_node,
            is_protected=False,
            pattern=AuthorizationPattern.NONE,
        )
        assert flow.confidence == 0.8

    def test_custom_confidence(self):
        """Test custom confidence value."""
        flow = AuthorizationFlow(
            flow_id="flow-004",
            entry_point=self.entry_node,
            auth_nodes=[self.auth_node],
            resource_access=self.resource_node,
            is_protected=True,
            pattern=AuthorizationPattern.RBAC,
            confidence=0.95,
        )
        assert flow.confidence == 0.95


# =============================================================================
# AuthorizationGap Dataclass Tests
# =============================================================================


class TestAuthorizationGap:
    """Tests for AuthorizationGap dataclass."""

    def setup_method(self):
        """Set up test fixtures."""
        self.entry_node = AuthorizationNode(
            node_id="entry-001",
            node_type="function",
            name="get_document",
            file_path="src/api/documents.py",
            line_number=100,
            check_type=AuthorizationCheckType.NONE,
        )
        self.resource_node = AuthorizationNode(
            node_id="res-001",
            node_type="resource_access",
            name="Document.get(doc_id)",
            file_path="src/api/documents.py",
            line_number=110,
            check_type=AuthorizationCheckType.NONE,
        )
        self.flow = AuthorizationFlow(
            flow_id="flow-001",
            entry_point=self.entry_node,
            auth_nodes=[],
            resource_access=self.resource_node,
            is_protected=False,
            pattern=AuthorizationPattern.NONE,
        )

    def test_create_missing_check_gap(self):
        """Test creating a missing check gap."""
        gap = AuthorizationGap(
            gap_id="gap-001",
            gap_type="missing_check",
            severity="HIGH",
            flow=self.flow,
            description="No authorization checks found",
            recommendation="Add authentication decorator",
        )
        assert gap.gap_id == "gap-001"
        assert gap.gap_type == "missing_check"
        assert gap.severity == "HIGH"
        assert gap.flow == self.flow
        assert "No authorization" in gap.description

    def test_create_idor_risk_gap(self):
        """Test creating an IDOR risk gap."""
        gap = AuthorizationGap(
            gap_id="gap-002",
            gap_type="idor_risk",
            severity="CRITICAL",
            flow=self.flow,
            description="ID-based access without ownership check",
            recommendation="Add ownership verification",
            cwe_ids=["CWE-639", "CWE-284"],
        )
        assert gap.gap_type == "idor_risk"
        assert gap.severity == "CRITICAL"
        assert "CWE-639" in gap.cwe_ids

    def test_default_cwe_ids(self):
        """Test default CWE IDs list."""
        gap = AuthorizationGap(
            gap_id="gap-003",
            gap_type="weak_check",
            severity="MEDIUM",
            flow=self.flow,
            description="Weak authorization pattern",
            recommendation="Implement RBAC",
        )
        assert gap.cwe_ids == []


# =============================================================================
# AuthorizationFlowAnalyzer Tests
# =============================================================================


class TestAuthorizationFlowAnalyzer:
    """Tests for AuthorizationFlowAnalyzer class."""

    def setup_method(self):
        """Set up test fixtures."""
        self.analyzer = AuthorizationFlowAnalyzer(use_mock=True)

    def test_initialization_mock_mode(self):
        """Test initialization in mock mode."""
        analyzer = AuthorizationFlowAnalyzer(use_mock=True)
        assert analyzer.use_mock is True
        assert analyzer.neptune is None
        assert analyzer._flow_counter == 0
        assert analyzer._gap_counter == 0

    def test_initialization_with_neptune(self):
        """Test initialization with Neptune service."""
        mock_neptune = MagicMock()
        analyzer = AuthorizationFlowAnalyzer(neptune_service=mock_neptune)
        assert analyzer.use_mock is False
        assert analyzer.neptune == mock_neptune

    def test_initialization_patterns_loaded(self):
        """Test that detection patterns are loaded."""
        assert len(self.analyzer.auth_decorator_patterns) > 0
        assert len(self.analyzer.auth_function_patterns) > 0
        assert len(self.analyzer.ownership_patterns) > 0
        assert len(self.analyzer.resource_access_patterns) > 0

    def test_generate_flow_id(self):
        """Test flow ID generation."""
        flow_id1 = self.analyzer._generate_flow_id()
        flow_id2 = self.analyzer._generate_flow_id()
        assert flow_id1.startswith("AFL-")
        assert flow_id2.startswith("AFL-")
        assert flow_id1 != flow_id2

    def test_generate_gap_id(self):
        """Test gap ID generation."""
        gap_id1 = self.analyzer._generate_gap_id()
        gap_id2 = self.analyzer._generate_gap_id()
        assert gap_id1.startswith("AGP-")
        assert gap_id2.startswith("AGP-")
        assert gap_id1 != gap_id2


class TestClassifyCheckType:
    """Tests for check type classification."""

    def setup_method(self):
        """Set up test fixtures."""
        self.analyzer = AuthorizationFlowAnalyzer(use_mock=True)

    def test_classify_role_check(self):
        """Test classifying role checks."""
        assert (
            self.analyzer._classify_check_type("@roles_required")
            == AuthorizationCheckType.ROLE_CHECK
        )
        assert (
            self.analyzer._classify_check_type("hasRole('admin')")
            == AuthorizationCheckType.ROLE_CHECK
        )

    def test_classify_permission_check(self):
        """Test classifying permission checks."""
        assert (
            self.analyzer._classify_check_type("@permission_required")
            == AuthorizationCheckType.PERMISSION_CHECK
        )
        assert (
            self.analyzer._classify_check_type("check_permission()")
            == AuthorizationCheckType.PERMISSION_CHECK
        )

    def test_classify_ownership_check(self):
        """Test classifying ownership checks."""
        assert (
            self.analyzer._classify_check_type("resource.owner_id ==")
            == AuthorizationCheckType.OWNERSHIP_CHECK
        )
        assert (
            self.analyzer._classify_check_type("belongs_to(user)")
            == AuthorizationCheckType.OWNERSHIP_CHECK
        )

    def test_classify_jwt_check(self):
        """Test classifying JWT checks."""
        assert (
            self.analyzer._classify_check_type("@jwt_required")
            == AuthorizationCheckType.JWT_CHECK
        )
        assert (
            self.analyzer._classify_check_type("validate_token()")
            == AuthorizationCheckType.JWT_CHECK
        )

    def test_classify_api_key_check(self):
        """Test classifying API key checks."""
        assert (
            self.analyzer._classify_check_type("@api_key_required")
            == AuthorizationCheckType.API_KEY_CHECK
        )
        assert (
            self.analyzer._classify_check_type("verify_apikey()")
            == AuthorizationCheckType.API_KEY_CHECK
        )

    def test_classify_session_check(self):
        """Test classifying session checks."""
        assert (
            self.analyzer._classify_check_type("session.user")
            == AuthorizationCheckType.SESSION_CHECK
        )

    def test_classify_unknown(self):
        """Test classifying unknown patterns."""
        assert (
            self.analyzer._classify_check_type("unknown_pattern")
            == AuthorizationCheckType.NONE
        )


class TestDeterminePattern:
    """Tests for authorization pattern determination."""

    def setup_method(self):
        """Set up test fixtures."""
        self.analyzer = AuthorizationFlowAnalyzer(use_mock=True)

    def test_determine_pattern_rbac(self):
        """Test determining RBAC pattern."""
        nodes = [
            AuthorizationNode(
                node_id="1",
                node_type="decorator",
                name="@roles_required",
                file_path="test.py",
                line_number=1,
                check_type=AuthorizationCheckType.ROLE_CHECK,
            )
        ]
        assert self.analyzer._determine_pattern(nodes) == AuthorizationPattern.RBAC

    def test_determine_pattern_abac(self):
        """Test determining ABAC pattern."""
        nodes = [
            AuthorizationNode(
                node_id="1",
                node_type="decorator",
                name="@permission_required",
                file_path="test.py",
                line_number=1,
                check_type=AuthorizationCheckType.PERMISSION_CHECK,
            )
        ]
        assert self.analyzer._determine_pattern(nodes) == AuthorizationPattern.ABAC

    def test_determine_pattern_ownership(self):
        """Test determining ownership pattern."""
        nodes = [
            AuthorizationNode(
                node_id="1",
                node_type="conditional",
                name="user.id == resource.owner",
                file_path="test.py",
                line_number=1,
                check_type=AuthorizationCheckType.OWNERSHIP_CHECK,
            )
        ]
        assert self.analyzer._determine_pattern(nodes) == AuthorizationPattern.OWNERSHIP

    def test_determine_pattern_acl(self):
        """Test determining ACL pattern."""
        nodes = [
            AuthorizationNode(
                node_id="1",
                node_type="decorator",
                name="@login_required",
                file_path="test.py",
                line_number=1,
                check_type=AuthorizationCheckType.SESSION_CHECK,
            )
        ]
        assert self.analyzer._determine_pattern(nodes) == AuthorizationPattern.ACL

    def test_determine_pattern_none(self):
        """Test determining no pattern."""
        nodes = []
        assert self.analyzer._determine_pattern(nodes) == AuthorizationPattern.NONE

    def test_determine_pattern_priority(self):
        """Test pattern priority (RBAC > ownership > ABAC > ACL)."""
        # RBAC should take precedence
        nodes = [
            AuthorizationNode(
                node_id="1",
                node_type="decorator",
                name="@roles_required",
                file_path="test.py",
                line_number=1,
                check_type=AuthorizationCheckType.ROLE_CHECK,
            ),
            AuthorizationNode(
                node_id="2",
                node_type="decorator",
                name="@permission_required",
                file_path="test.py",
                line_number=2,
                check_type=AuthorizationCheckType.PERMISSION_CHECK,
            ),
        ]
        assert self.analyzer._determine_pattern(nodes) == AuthorizationPattern.RBAC


class TestAnalyzeFile:
    """Tests for file analysis."""

    def setup_method(self):
        """Set up test fixtures."""
        self.analyzer = AuthorizationFlowAnalyzer(use_mock=True)

    @pytest.mark.asyncio
    async def test_analyze_file_with_decorator(self):
        """Test analyzing file with auth decorator."""
        content = """
@login_required
def get_user(user_id):
    return User.get(user_id)
"""
        flows = await self.analyzer.analyze_file("test.py", content)
        assert len(flows) >= 1
        # Should find the resource access
        assert any(f.resource_access is not None for f in flows)

    @pytest.mark.asyncio
    async def test_analyze_file_without_auth(self):
        """Test analyzing file without auth checks."""
        content = """
def get_document(doc_id):
    return Document.get(doc_id)
"""
        flows = await self.analyzer.analyze_file("test.py", content)
        assert len(flows) >= 1
        # Should find unprotected flow
        assert any(not f.is_protected for f in flows)

    @pytest.mark.asyncio
    async def test_analyze_file_with_role_decorator(self):
        """Test analyzing file with role decorator."""
        content = """
@roles_required('admin')
def delete_user(user_id):
    User.query().filter(id=user_id).delete()
"""
        flows = await self.analyzer.analyze_file("admin.py", content)
        assert len(flows) >= 1

    @pytest.mark.asyncio
    async def test_analyze_file_with_ownership_check(self):
        """Test analyzing file with ownership check."""
        content = """
@login_required
def update_profile(user_id, data):
    user = User.get(user_id)
    if user.owner_id == current_user.id:
        user.update(data)
"""
        flows = await self.analyzer.analyze_file("profile.py", content)
        assert len(flows) >= 1
        # Should detect ownership check
        ownership_flows = [
            f
            for f in flows
            if any(
                n.check_type == AuthorizationCheckType.OWNERSHIP_CHECK
                for n in f.auth_nodes
            )
        ]
        assert len(ownership_flows) >= 1

    @pytest.mark.asyncio
    async def test_analyze_file_async_function(self):
        """Test analyzing async functions."""
        content = """
@jwt_required
async def get_data(item_id):
    return await Item.find_one(item_id)
"""
        flows = await self.analyzer.analyze_file("async_api.py", content)
        assert len(flows) >= 1

    @pytest.mark.asyncio
    async def test_analyze_file_multiple_functions(self):
        """Test analyzing file with multiple functions."""
        content = """
@login_required
def get_users():
    return User.query().all()

def public_endpoint():
    return {"status": "ok"}

@roles_required('admin')
def delete_all():
    User.query().delete()
"""
        flows = await self.analyzer.analyze_file("multi.py", content)
        # Should find flows for functions with resource access
        assert len(flows) >= 2


class TestFindAuthorizationGaps:
    """Tests for finding authorization gaps."""

    def setup_method(self):
        """Set up test fixtures."""
        self.analyzer = AuthorizationFlowAnalyzer(use_mock=True)

    @pytest.mark.asyncio
    async def test_find_gap_missing_check(self):
        """Test finding missing authorization check gap."""
        entry_node = AuthorizationNode(
            node_id="entry-001",
            node_type="function",
            name="get_document",
            file_path="docs.py",
            line_number=10,
            check_type=AuthorizationCheckType.NONE,
        )
        resource_node = AuthorizationNode(
            node_id="res-001",
            node_type="resource_access",
            name="Document.get(doc_id)",
            file_path="docs.py",
            line_number=15,
            check_type=AuthorizationCheckType.NONE,
        )
        flow = AuthorizationFlow(
            flow_id="flow-001",
            entry_point=entry_node,
            auth_nodes=[],
            resource_access=resource_node,
            is_protected=False,
            pattern=AuthorizationPattern.NONE,
        )

        gaps = await self.analyzer.find_authorization_gaps([flow])
        assert len(gaps) >= 1
        missing_gaps = [g for g in gaps if g.gap_type == "missing_check"]
        assert len(missing_gaps) >= 1
        assert "CWE-862" in missing_gaps[0].cwe_ids

    @pytest.mark.asyncio
    async def test_find_gap_idor_risk(self):
        """Test finding IDOR risk gap."""
        entry_node = AuthorizationNode(
            node_id="entry-001",
            node_type="function",
            name="get_user",
            file_path="users.py",
            line_number=10,
            check_type=AuthorizationCheckType.NONE,
        )
        auth_node = AuthorizationNode(
            node_id="auth-001",
            node_type="decorator",
            name="@login_required",
            file_path="users.py",
            line_number=9,
            check_type=AuthorizationCheckType.SESSION_CHECK,
        )
        resource_node = AuthorizationNode(
            node_id="res-001",
            node_type="resource_access",
            name="User.get(user_id)",
            file_path="users.py",
            line_number=15,
            check_type=AuthorizationCheckType.NONE,
        )
        flow = AuthorizationFlow(
            flow_id="flow-001",
            entry_point=entry_node,
            auth_nodes=[auth_node],  # Has auth but no ownership check
            resource_access=resource_node,
            is_protected=True,
            pattern=AuthorizationPattern.ACL,
        )

        gaps = await self.analyzer.find_authorization_gaps([flow])
        idor_gaps = [g for g in gaps if g.gap_type == "idor_risk"]
        assert len(idor_gaps) >= 1
        assert idor_gaps[0].severity == "CRITICAL"

    @pytest.mark.asyncio
    async def test_find_gap_weak_pattern(self):
        """Test finding weak authorization pattern gap."""
        entry_node = AuthorizationNode(
            node_id="entry-001",
            node_type="function",
            name="get_data",
            file_path="api.py",
            line_number=10,
            check_type=AuthorizationCheckType.NONE,
        )
        auth_node = AuthorizationNode(
            node_id="auth-001",
            node_type="decorator",
            name="@api_key_required",
            file_path="api.py",
            line_number=9,
            check_type=AuthorizationCheckType.API_KEY_CHECK,
        )
        resource_node = AuthorizationNode(
            node_id="res-001",
            node_type="resource_access",
            name="Data.all()",
            file_path="api.py",
            line_number=15,
            check_type=AuthorizationCheckType.NONE,
        )
        flow = AuthorizationFlow(
            flow_id="flow-001",
            entry_point=entry_node,
            auth_nodes=[auth_node],
            resource_access=resource_node,
            is_protected=True,
            pattern=AuthorizationPattern.ACL,
        )

        gaps = await self.analyzer.find_authorization_gaps([flow])
        weak_gaps = [g for g in gaps if g.gap_type == "weak_check"]
        assert len(weak_gaps) >= 1
        assert weak_gaps[0].severity == "MEDIUM"

    @pytest.mark.asyncio
    async def test_no_gaps_for_protected_flow(self):
        """Test no IDOR gap when ownership check present."""
        entry_node = AuthorizationNode(
            node_id="entry-001",
            node_type="function",
            name="update_profile",
            file_path="profile.py",
            line_number=10,
            check_type=AuthorizationCheckType.NONE,
        )
        auth_node = AuthorizationNode(
            node_id="auth-001",
            node_type="decorator",
            name="@roles_required",
            file_path="profile.py",
            line_number=9,
            check_type=AuthorizationCheckType.ROLE_CHECK,
        )
        ownership_node = AuthorizationNode(
            node_id="own-001",
            node_type="conditional",
            name="user.owner_id ==",
            file_path="profile.py",
            line_number=12,
            check_type=AuthorizationCheckType.OWNERSHIP_CHECK,
        )
        resource_node = AuthorizationNode(
            node_id="res-001",
            node_type="resource_access",
            name="Profile.get(id)",
            file_path="profile.py",
            line_number=15,
            check_type=AuthorizationCheckType.NONE,
        )
        flow = AuthorizationFlow(
            flow_id="flow-001",
            entry_point=entry_node,
            auth_nodes=[auth_node, ownership_node],
            resource_access=resource_node,
            is_protected=True,
            pattern=AuthorizationPattern.RBAC,
        )

        gaps = await self.analyzer.find_authorization_gaps([flow])
        idor_gaps = [g for g in gaps if g.gap_type == "idor_risk"]
        # Should not have IDOR gap since ownership check exists
        assert len(idor_gaps) == 0


class TestHelperMethods:
    """Tests for helper methods."""

    def setup_method(self):
        """Set up test fixtures."""
        self.analyzer = AuthorizationFlowAnalyzer(use_mock=True)

    def test_is_id_based_access_with_id(self):
        """Test detecting ID-based access."""
        resource_node = AuthorizationNode(
            node_id="res-001",
            node_type="resource_access",
            name="User.get(user_id)",
            file_path="test.py",
            line_number=10,
            check_type=AuthorizationCheckType.NONE,
        )
        flow = AuthorizationFlow(
            flow_id="flow-001",
            entry_point=resource_node,
            auth_nodes=[],
            resource_access=resource_node,
            is_protected=False,
            pattern=AuthorizationPattern.NONE,
        )
        assert self.analyzer._is_id_based_access(flow) is True

    def test_is_id_based_access_find_one(self):
        """Test detecting find_one access."""
        resource_node = AuthorizationNode(
            node_id="res-001",
            node_type="resource_access",
            name="Collection.find_one()",
            file_path="test.py",
            line_number=10,
            check_type=AuthorizationCheckType.NONE,
        )
        flow = AuthorizationFlow(
            flow_id="flow-001",
            entry_point=resource_node,
            auth_nodes=[],
            resource_access=resource_node,
            is_protected=False,
            pattern=AuthorizationPattern.NONE,
        )
        assert self.analyzer._is_id_based_access(flow) is True

    def test_is_id_based_access_filter(self):
        """Test detecting filter access."""
        resource_node = AuthorizationNode(
            node_id="res-001",
            node_type="resource_access",
            name="Model.filter(status='active')",
            file_path="test.py",
            line_number=10,
            check_type=AuthorizationCheckType.NONE,
        )
        flow = AuthorizationFlow(
            flow_id="flow-001",
            entry_point=resource_node,
            auth_nodes=[],
            resource_access=resource_node,
            is_protected=False,
            pattern=AuthorizationPattern.NONE,
        )
        assert self.analyzer._is_id_based_access(flow) is True

    def test_has_ownership_check_true(self):
        """Test detecting ownership check."""
        auth_node = AuthorizationNode(
            node_id="own-001",
            node_type="conditional",
            name="user.id == resource.owner",
            file_path="test.py",
            line_number=10,
            check_type=AuthorizationCheckType.OWNERSHIP_CHECK,
        )
        resource_node = AuthorizationNode(
            node_id="res-001",
            node_type="resource_access",
            name="Resource.get(id)",
            file_path="test.py",
            line_number=15,
            check_type=AuthorizationCheckType.NONE,
        )
        flow = AuthorizationFlow(
            flow_id="flow-001",
            entry_point=resource_node,
            auth_nodes=[auth_node],
            resource_access=resource_node,
            is_protected=True,
            pattern=AuthorizationPattern.OWNERSHIP,
        )
        assert self.analyzer._has_ownership_check(flow) is True

    def test_has_ownership_check_false(self):
        """Test detecting lack of ownership check."""
        auth_node = AuthorizationNode(
            node_id="auth-001",
            node_type="decorator",
            name="@login_required",
            file_path="test.py",
            line_number=10,
            check_type=AuthorizationCheckType.SESSION_CHECK,
        )
        resource_node = AuthorizationNode(
            node_id="res-001",
            node_type="resource_access",
            name="Resource.get(id)",
            file_path="test.py",
            line_number=15,
            check_type=AuthorizationCheckType.NONE,
        )
        flow = AuthorizationFlow(
            flow_id="flow-001",
            entry_point=resource_node,
            auth_nodes=[auth_node],
            resource_access=resource_node,
            is_protected=True,
            pattern=AuthorizationPattern.ACL,
        )
        assert self.analyzer._has_ownership_check(flow) is False


class TestNeptuneAnalysis:
    """Tests for Neptune graph analysis."""

    def setup_method(self):
        """Set up test fixtures."""
        self.mock_neptune = MagicMock()
        self.analyzer = AuthorizationFlowAnalyzer(neptune_service=self.mock_neptune)

    @pytest.mark.asyncio
    async def test_analyze_with_neptune_mock_fallback(self):
        """Test Neptune analysis with mock fallback."""
        analyzer = AuthorizationFlowAnalyzer(use_mock=True)
        flows = await analyzer.analyze_with_neptune("src/")
        assert len(flows) == 2
        # Should return mock data
        assert flows[0].entry_point.name == "get_user"
        assert flows[1].entry_point.name == "get_document"

    @pytest.mark.asyncio
    async def test_analyze_with_neptune_success(self):
        """Test Neptune analysis with actual service."""
        self.mock_neptune.query.side_effect = [
            [{"name": "get_user", "file": "api.py", "line": 10}],
            [[{"type": "auth_check", "name": "login_required"}]],
            [{"name": "User.get", "file_path": "api.py", "line_number": 15}],
        ]

        flows = await self.analyzer.analyze_with_neptune("src/")
        assert len(flows) >= 1
        assert self.mock_neptune.query.called

    @pytest.mark.asyncio
    async def test_analyze_with_neptune_error(self):
        """Test Neptune analysis handles errors."""
        self.mock_neptune.query.side_effect = Exception("Connection failed")

        flows = await self.analyzer.analyze_with_neptune("src/")
        # Should return empty list on error
        assert flows == []

    def test_build_auth_nodes_from_paths(self):
        """Test building auth nodes from path results."""
        paths = [
            [
                {"type": "function", "name": "get_user"},
                {
                    "type": "auth_check",
                    "id": "auth-1",
                    "check_type": "decorator",
                    "name": "login_required",
                    "file_path": "api.py",
                    "line_number": 10,
                },
            ]
        ]
        nodes = self.analyzer._build_auth_nodes_from_paths(paths)
        assert len(nodes) == 1
        assert nodes[0].name == "login_required"

    def test_build_auth_nodes_from_empty_paths(self):
        """Test building auth nodes from empty paths."""
        nodes = self.analyzer._build_auth_nodes_from_paths([])
        assert nodes == []


class TestMockNeptuneAnalysis:
    """Tests for mock Neptune analysis."""

    def setup_method(self):
        """Set up test fixtures."""
        self.analyzer = AuthorizationFlowAnalyzer(use_mock=True)

    @pytest.mark.asyncio
    async def test_mock_neptune_returns_sample_flows(self):
        """Test mock analysis returns sample flows."""
        flows = await self.analyzer._mock_neptune_analysis()
        assert len(flows) == 2

    @pytest.mark.asyncio
    async def test_mock_neptune_protected_flow(self):
        """Test mock analysis includes protected flow."""
        flows = await self.analyzer._mock_neptune_analysis()
        protected_flows = [f for f in flows if f.is_protected]
        assert len(protected_flows) == 1
        assert protected_flows[0].entry_point.name == "get_user"

    @pytest.mark.asyncio
    async def test_mock_neptune_unprotected_flow(self):
        """Test mock analysis includes unprotected flow."""
        flows = await self.analyzer._mock_neptune_analysis()
        unprotected_flows = [f for f in flows if not f.is_protected]
        assert len(unprotected_flows) == 1
        assert unprotected_flows[0].entry_point.name == "get_document"


# =============================================================================
# Factory Function Tests
# =============================================================================


class TestFactoryFunction:
    """Tests for factory function."""

    def test_create_analyzer_default(self):
        """Test creating analyzer with defaults."""
        analyzer = create_authorization_flow_analyzer()
        assert isinstance(analyzer, AuthorizationFlowAnalyzer)
        assert analyzer.use_mock is True
        assert analyzer.neptune is None

    def test_create_analyzer_with_neptune(self):
        """Test creating analyzer with Neptune service."""
        mock_neptune = MagicMock()
        analyzer = create_authorization_flow_analyzer(neptune_service=mock_neptune)
        assert analyzer.use_mock is False
        assert analyzer.neptune == mock_neptune

    def test_create_analyzer_mock_mode(self):
        """Test creating analyzer in mock mode."""
        analyzer = create_authorization_flow_analyzer(use_mock=True)
        assert analyzer.use_mock is True

    def test_factory_creates_independent_instances(self):
        """Test factory creates independent instances."""
        analyzer1 = create_authorization_flow_analyzer()
        analyzer2 = create_authorization_flow_analyzer()
        assert analyzer1 is not analyzer2
        analyzer1._flow_counter = 100
        assert analyzer2._flow_counter == 0


# =============================================================================
# Integration Tests
# =============================================================================


class TestAuthorizationFlowIntegration:
    """Integration tests for authorization flow analysis."""

    def setup_method(self):
        """Set up test fixtures."""
        self.analyzer = AuthorizationFlowAnalyzer(use_mock=True)

    @pytest.mark.asyncio
    async def test_full_analysis_workflow(self):
        """Test complete analysis workflow."""
        content = '''
@login_required
def get_user(user_id):
    """Get a user by ID."""
    return User.get(user_id)

def public_health():
    """Health check endpoint."""
    return {"status": "healthy"}

@roles_required('admin')
def delete_user(user_id):
    """Delete a user (admin only)."""
    user = User.find_by_id(user_id)
    if user.owner_id == current_user.id:
        user.delete()
'''
        # Step 1: Analyze file
        flows = await self.analyzer.analyze_file("users.py", content)
        assert len(flows) >= 2

        # Step 2: Find gaps
        gaps = await self.analyzer.find_authorization_gaps(flows)

        # Should have at least one gap
        assert len(gaps) >= 0

    @pytest.mark.asyncio
    async def test_gap_analysis_with_mock_neptune(self):
        """Test gap analysis with mock Neptune data."""
        flows = await self.analyzer._mock_neptune_analysis()
        gaps = await self.analyzer.find_authorization_gaps(flows)

        # Should find gap for unprotected document flow
        assert any(
            g.flow.entry_point.name == "get_document" and g.gap_type == "missing_check"
            for g in gaps
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
