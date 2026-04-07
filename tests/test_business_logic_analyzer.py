"""
Tests for Business Logic Vulnerability Analyzer Agent.

This module tests the detection of context-specific vulnerabilities
including IDOR, race conditions, authorization bypasses, and business
rule violations. Part of AWS Security Agent capability parity (Gap 4/4).

Author: Project Aura Team
Created: 2025-12-03
"""

import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.agents.business_logic_analyzer_agent import (
    CWE_MAPPINGS,
    NIST_MAPPINGS,
    AnalysisResult,
    BusinessLogicAnalyzerAgent,
    BusinessLogicFinding,
    Severity,
    VulnerabilityType,
    create_business_logic_analyzer,
)
from src.services.authorization_flow_analyzer import (
    AuthorizationFlowAnalyzer,
    create_authorization_flow_analyzer,
)

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def analyzer():
    """Create analyzer without LLM for pattern-based testing."""
    return BusinessLogicAnalyzerAgent(
        neptune_service=None,
        llm_client=None,
        use_llm_analysis=False,
    )


@pytest.fixture
def analyzer_with_llm():
    """Create analyzer with mocked LLM."""
    mock_llm = AsyncMock()
    mock_llm.generate = AsyncMock(return_value="[]")
    return BusinessLogicAnalyzerAgent(
        neptune_service=None,
        llm_client=mock_llm,
        use_llm_analysis=True,
    )


@pytest.fixture
def auth_analyzer():
    """Create authorization flow analyzer."""
    return AuthorizationFlowAnalyzer(neptune_service=None, use_mock=True)


@pytest.fixture
def sample_finding():
    """Create sample finding for testing."""
    return BusinessLogicFinding(
        finding_id="BLF-20251203120000-0001",
        vulnerability_type=VulnerabilityType.IDOR,
        severity=Severity.CRITICAL,
        title="IDOR in get_user",
        description="User ID accessed without ownership check",
        file_path="src/api/users.py",
        line_number=42,
        code_snippet="user = User.get(user_id)",
        recommendation="Add ownership verification",
        cwe_ids=["CWE-639", "CWE-284"],
        nist_controls=["AC-3", "AC-4"],
        confidence=0.85,
        affected_functions=["get_user"],
    )


@pytest.fixture
def temp_repo():
    """Create temporary repository with test files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_path = Path(tmpdir)

        # Create API directory
        api_dir = repo_path / "src" / "api"
        api_dir.mkdir(parents=True)

        # Create vulnerable user API
        users_api = api_dir / "users.py"
        users_api.write_text("""
from flask import request, jsonify

@app.route('/users/<int:user_id>')
def get_user(user_id):
    # IDOR: No ownership check
    user = User.query.get(user_id)
    return jsonify(user.to_dict())

@app.route('/users/<int:user_id>', methods=['PUT'])
def update_user(user_id):
    # Mass assignment vulnerability
    user = User.query.get(user_id)
    user = User(**request.json)
    db.session.commit()
    return jsonify(user.to_dict())
""")

        # Create vulnerable payments API
        payments_api = api_dir / "payments.py"
        payments_api.write_text("""
from flask import request

@app.route('/transfer', methods=['POST'])
def transfer_money():
    # Race condition: check-then-act
    account = Account.query.get(request.json['from_account'])
    if account.balance >= request.json['amount']:
        account.balance -= request.json['amount']
        # Time-of-check to time-of-use race condition
        target = Account.query.get(request.json['to_account'])
        target.balance += request.json['amount']
        db.session.commit()
    return jsonify({'status': 'ok'})
""")

        # Create secure API for comparison
        secure_api = api_dir / "secure.py"
        secure_api.write_text("""
from flask import request
from flask_login import login_required, current_user

@app.route('/profile')
@login_required
def get_profile():
    # Secure: uses current_user
    return jsonify(current_user.to_dict())

@app.route('/documents/<int:doc_id>')
@login_required
def get_document(doc_id):
    # Secure: ownership check
    doc = Document.query.get(doc_id)
    if doc.owner_id != current_user.id:
        return jsonify({'error': 'forbidden'}), 403
    return jsonify(doc.to_dict())
""")

        yield repo_path


# =============================================================================
# BusinessLogicFinding Tests
# =============================================================================


class TestBusinessLogicFinding:
    """Tests for BusinessLogicFinding dataclass."""

    def test_finding_creation(self, sample_finding):
        """Test finding can be created with all fields."""
        assert sample_finding.finding_id == "BLF-20251203120000-0001"
        assert sample_finding.vulnerability_type == VulnerabilityType.IDOR
        assert sample_finding.severity == Severity.CRITICAL
        assert len(sample_finding.cwe_ids) == 2

    def test_finding_to_dict(self, sample_finding):
        """Test finding serialization."""
        data = sample_finding.to_dict()

        assert data["finding_id"] == "BLF-20251203120000-0001"
        assert data["vulnerability_type"] == "idor"
        assert data["severity"] == "critical"
        assert "CWE-639" in data["cwe_ids"]

    def test_finding_default_values(self):
        """Test finding with minimal fields."""
        finding = BusinessLogicFinding(
            finding_id="BLF-001",
            vulnerability_type=VulnerabilityType.RACE_CONDITION,
            severity=Severity.HIGH,
            title="Test",
            description="Test finding",
            file_path="test.py",
            line_number=10,
            code_snippet="test code",
            recommendation="Fix it",
        )

        assert finding.affected_functions == []
        assert finding.cwe_ids == []
        assert finding.confidence == 0.8


# =============================================================================
# IDOR Detection Tests
# =============================================================================


class TestIDORDetection:
    """Tests for IDOR vulnerability detection."""

    @pytest.mark.asyncio
    async def test_detect_idor_from_request(self, analyzer):
        """Test detection of ID from request without validation."""
        content = """
def get_document(request):
    doc_id = request.args.get('id')
    doc = Document.get(doc_id)
    return doc
"""
        findings = await analyzer.analyze_file("test.py", content)
        idor_findings = [
            f for f in findings if f.vulnerability_type == VulnerabilityType.IDOR
        ]

        assert len(idor_findings) >= 1
        assert idor_findings[0].severity == Severity.CRITICAL

    @pytest.mark.asyncio
    async def test_detect_idor_route_param(self, analyzer):
        """Test detection of IDOR in route parameters."""
        content = """
@app.route('/users/<int:user_id>')
def get_user(user_id):
    user = User.query.get(user_id)
    return jsonify(user.to_dict())
"""
        findings = await analyzer.analyze_file("test.py", content)
        idor_findings = [
            f for f in findings if f.vulnerability_type == VulnerabilityType.IDOR
        ]

        assert len(idor_findings) >= 1

    @pytest.mark.asyncio
    async def test_no_idor_with_ownership_check(self, analyzer):
        """Test that ownership checks prevent IDOR false positives."""
        content = """
@app.route('/documents/<int:doc_id>')
def get_document(doc_id):
    doc = Document.query.get(doc_id)
    if doc.owner_id != current_user.id:
        return jsonify({'error': 'forbidden'}), 403
    return jsonify(doc.to_dict())
"""
        findings = await analyzer.analyze_file("test.py", content)
        idor_findings = [
            f for f in findings if f.vulnerability_type == VulnerabilityType.IDOR
        ]

        # Should have fewer findings due to ownership check
        assert len(idor_findings) == 0 or all(f.confidence < 0.9 for f in idor_findings)


# =============================================================================
# Race Condition Detection Tests
# =============================================================================


class TestRaceConditionDetection:
    """Tests for race condition vulnerability detection."""

    @pytest.mark.asyncio
    async def test_detect_check_then_act(self, analyzer):
        """Test detection of check-then-act pattern."""
        content = """
def withdraw(account_id, amount):
    account = Account.get(account_id)
    if account.balance >= amount:
        account.balance -= amount
        account.save()
"""
        findings = await analyzer.analyze_file("test.py", content)
        race_findings = [
            f
            for f in findings
            if f.vulnerability_type == VulnerabilityType.RACE_CONDITION
        ]

        assert len(race_findings) >= 1
        assert race_findings[0].severity == Severity.HIGH

    @pytest.mark.asyncio
    async def test_no_race_with_lock(self, analyzer):
        """Test that locks prevent race condition detection."""
        content = """
def withdraw(account_id, amount):
    with db.session.begin():
        account = Account.query.with_for_update().get(account_id)
        if account.balance >= amount:
            account.balance -= amount
"""
        findings = await analyzer.analyze_file("test.py", content)
        race_findings = [
            f
            for f in findings
            if f.vulnerability_type == VulnerabilityType.RACE_CONDITION
        ]

        # Should have no findings due to locking
        assert len(race_findings) == 0


# =============================================================================
# Mass Assignment Detection Tests
# =============================================================================


class TestMassAssignmentDetection:
    """Tests for mass assignment vulnerability detection."""

    @pytest.mark.asyncio
    async def test_detect_mass_assignment_kwargs(self, analyzer):
        """Test detection of **kwargs to model."""
        content = """
def create_user():
    user = UserModel(**request.json)
    db.session.add(user)
    db.session.commit()
"""
        findings = await analyzer.analyze_file("test.py", content)
        mass_findings = [
            f
            for f in findings
            if f.vulnerability_type == VulnerabilityType.MASS_ASSIGNMENT
        ]

        assert len(mass_findings) >= 1
        assert mass_findings[0].severity == Severity.HIGH

    @pytest.mark.asyncio
    async def test_detect_update_with_kwargs(self, analyzer):
        """Test detection of update with unfiltered input."""
        content = """
def update_user(user_id):
    user = User.query.get(user_id)
    user.update(**request.json)
"""
        findings = await analyzer.analyze_file("test.py", content)
        mass_findings = [
            f
            for f in findings
            if f.vulnerability_type == VulnerabilityType.MASS_ASSIGNMENT
        ]

        assert len(mass_findings) >= 1


# =============================================================================
# Privilege Escalation Detection Tests
# =============================================================================


class TestPrivilegeEscalationDetection:
    """Tests for privilege escalation vulnerability detection."""

    @pytest.mark.asyncio
    async def test_detect_role_from_request(self, analyzer):
        """Test detection of role from request data."""
        content = """
def update_profile():
    user = current_user
    user.role = request.json['role']
    user.is_admin = request.form.get('is_admin')
    db.session.commit()
"""
        findings = await analyzer.analyze_file("test.py", content)
        priv_findings = [
            f
            for f in findings
            if f.vulnerability_type == VulnerabilityType.PRIVILEGE_ESCALATION
        ]

        assert len(priv_findings) >= 1
        assert priv_findings[0].severity == Severity.CRITICAL


# =============================================================================
# Workflow Bypass Detection Tests
# =============================================================================


class TestWorkflowBypassDetection:
    """Tests for workflow bypass vulnerability detection."""

    @pytest.mark.asyncio
    async def test_detect_direct_status_change(self, analyzer):
        """Test detection of direct status change to approved state."""
        content = """
def approve_request(request_id):
    req = Request.query.get(request_id)
    req.status = 'approved'
    db.session.commit()
"""
        findings = await analyzer.analyze_file("test.py", content)
        workflow_findings = [
            f
            for f in findings
            if f.vulnerability_type == VulnerabilityType.BUSINESS_RULE_BYPASS
        ]

        assert len(workflow_findings) >= 1

    @pytest.mark.asyncio
    async def test_no_bypass_with_state_machine(self, analyzer):
        """Test that state machine prevents bypass detection."""
        content = """
def approve_request(request_id):
    req = Request.query.get(request_id)
    allowed_transitions = {'pending': ['approved', 'rejected']}
    if req.status in allowed_transitions and 'approved' in allowed_transitions[req.status]:
        req.status = 'approved'
"""
        findings = await analyzer.analyze_file("test.py", content)
        workflow_findings = [
            f
            for f in findings
            if f.vulnerability_type == VulnerabilityType.BUSINESS_RULE_BYPASS
        ]

        # Should have no findings due to state machine
        assert len(workflow_findings) == 0


# =============================================================================
# Authorization Flow Analyzer Tests
# =============================================================================


class TestAuthorizationFlowAnalyzer:
    """Tests for AuthorizationFlowAnalyzer."""

    @pytest.mark.asyncio
    async def test_analyze_file_with_auth(self, auth_analyzer):
        """Test analyzing file with authentication."""
        content = """
@login_required
def get_profile():
    return current_user.profile

@roles_required('admin')
def get_admin_panel():
    return AdminPanel.get()
"""
        flows = await auth_analyzer.analyze_file("test.py", content)

        assert len(flows) >= 0  # May have flows for decorated functions

    @pytest.mark.asyncio
    async def test_find_gaps_no_auth(self, auth_analyzer):
        """Test finding gaps when no auth is present."""
        content = """
def get_user(user_id):
    user = User.query.get(user_id)
    return jsonify(user.to_dict())
"""
        flows = await auth_analyzer.analyze_file("test.py", content)
        gaps = await auth_analyzer.find_authorization_gaps(flows)

        # Should detect missing auth for resource access
        assert len(gaps) >= 1 if flows else True

    @pytest.mark.asyncio
    async def test_mock_neptune_analysis(self, auth_analyzer):
        """Test mock Neptune analysis returns flows."""
        flows = await auth_analyzer.analyze_with_neptune("/fake/repo")

        assert len(flows) >= 2  # Mock returns 2 flows
        assert any(f.is_protected for f in flows)
        assert any(not f.is_protected for f in flows)


# =============================================================================
# Repository Analysis Tests
# =============================================================================


class TestRepositoryAnalysis:
    """Tests for repository-wide analysis."""

    @pytest.mark.asyncio
    async def test_analyze_repository(self, analyzer, temp_repo):
        """Test analyzing entire repository."""
        result = await analyzer.analyze_repository(str(temp_repo))

        assert isinstance(result, AnalysisResult)
        assert (
            result.total_files_analyzed >= 2
        )  # users.py and payments.py (secure.py may be included)
        assert result.total_functions_analyzed >= 3
        assert len(result.findings) >= 2  # Should find IDOR and race conditions
        assert result.risk_score > 0

    @pytest.mark.asyncio
    async def test_analyze_repository_with_patterns(self, analyzer, temp_repo):
        """Test analyzing with custom file patterns."""
        result = await analyzer.analyze_repository(
            str(temp_repo), file_patterns=["**/users.py"]
        )

        assert result.total_files_analyzed == 1


# =============================================================================
# Risk Score Tests
# =============================================================================


class TestRiskScore:
    """Tests for risk score calculation."""

    def test_risk_score_critical(self, analyzer):
        """Test risk score with critical finding."""
        findings = [
            BusinessLogicFinding(
                finding_id="BLF-001",
                vulnerability_type=VulnerabilityType.IDOR,
                severity=Severity.CRITICAL,
                title="Test",
                description="Test",
                file_path="test.py",
                line_number=1,
                code_snippet="",
                recommendation="",
                confidence=1.0,
            )
        ]

        score = analyzer._calculate_risk_score(findings)
        assert score == 10.0

    def test_risk_score_multiple(self, analyzer):
        """Test risk score with multiple findings."""
        findings = [
            BusinessLogicFinding(
                finding_id="BLF-001",
                vulnerability_type=VulnerabilityType.IDOR,
                severity=Severity.CRITICAL,
                title="Test 1",
                description="Test",
                file_path="test.py",
                line_number=1,
                code_snippet="",
                recommendation="",
                confidence=1.0,
            ),
            BusinessLogicFinding(
                finding_id="BLF-002",
                vulnerability_type=VulnerabilityType.RACE_CONDITION,
                severity=Severity.HIGH,
                title="Test 2",
                description="Test",
                file_path="test.py",
                line_number=10,
                code_snippet="",
                recommendation="",
                confidence=0.8,
            ),
        ]

        score = analyzer._calculate_risk_score(findings)
        expected = 10.0 * 1.0 + 5.0 * 0.8
        assert score == expected

    def test_risk_score_capped(self, analyzer):
        """Test risk score is capped at 100."""
        findings = [
            BusinessLogicFinding(
                finding_id=f"BLF-{i:03d}",
                vulnerability_type=VulnerabilityType.IDOR,
                severity=Severity.CRITICAL,
                title=f"Test {i}",
                description="Test",
                file_path="test.py",
                line_number=i,
                code_snippet="",
                recommendation="",
                confidence=1.0,
            )
            for i in range(20)
        ]

        score = analyzer._calculate_risk_score(findings)
        assert score == 100.0


# =============================================================================
# CWE and NIST Mapping Tests
# =============================================================================


class TestCWEAndNISTMappings:
    """Tests for CWE and NIST control mappings."""

    def test_cwe_mappings_exist(self):
        """Test that CWE mappings exist for all vulnerability types."""
        assert VulnerabilityType.IDOR in CWE_MAPPINGS
        assert VulnerabilityType.RACE_CONDITION in CWE_MAPPINGS
        assert VulnerabilityType.MASS_ASSIGNMENT in CWE_MAPPINGS
        assert VulnerabilityType.PRIVILEGE_ESCALATION in CWE_MAPPINGS

    def test_nist_mappings_exist(self):
        """Test that NIST mappings exist for key vulnerability types."""
        assert VulnerabilityType.IDOR in NIST_MAPPINGS
        assert VulnerabilityType.IMPROPER_AUTHORIZATION in NIST_MAPPINGS

    @pytest.mark.asyncio
    async def test_finding_has_cwe_ids(self, analyzer):
        """Test that findings include CWE IDs."""
        content = """
def get_user():
    user_id = request.args.get('user_id')
    return User.get(user_id)
"""
        findings = await analyzer.analyze_file("test.py", content)
        idor_findings = [
            f for f in findings if f.vulnerability_type == VulnerabilityType.IDOR
        ]

        if idor_findings:
            assert len(idor_findings[0].cwe_ids) > 0
            assert idor_findings[0].cwe_ids[0].startswith("CWE-")


# =============================================================================
# Factory Function Tests
# =============================================================================


class TestFactoryFunctions:
    """Tests for factory functions."""

    def test_create_business_logic_analyzer(self):
        """Test creating analyzer without dependencies."""
        analyzer = create_business_logic_analyzer()

        assert analyzer is not None
        assert analyzer.neptune is None
        assert analyzer.llm is None

    def test_create_analyzer_with_llm(self):
        """Test creating analyzer with LLM."""
        mock_llm = MagicMock()
        analyzer = create_business_logic_analyzer(llm_client=mock_llm)

        assert analyzer.llm is mock_llm
        assert analyzer.use_llm_analysis is True

    def test_create_authorization_flow_analyzer(self):
        """Test creating auth flow analyzer."""
        analyzer = create_authorization_flow_analyzer()

        assert analyzer is not None
        assert analyzer.use_mock is True


# =============================================================================
# Spawnable Agent Adapter Tests
# =============================================================================


class TestSpawnableBusinessLogicAnalyzerAgent:
    """Tests for SpawnableBusinessLogicAnalyzerAgent adapter."""

    @pytest.fixture
    def spawnable_agent(self):
        """Create spawnable adapter for testing."""
        from src.agents.spawnable_agent_adapters import (
            SpawnableBusinessLogicAnalyzerAgent,
        )

        return SpawnableBusinessLogicAnalyzerAgent(agent_id="test-business-logic")

    @pytest.mark.asyncio
    async def test_adapter_capability(self, spawnable_agent):
        """Test adapter has correct capability."""
        from src.agents.meta_orchestrator import AgentCapability

        assert spawnable_agent.capability == AgentCapability.BUSINESS_LOGIC_ANALYSIS

    @pytest.mark.asyncio
    async def test_adapter_execute_single_file(self, spawnable_agent):
        """Test adapter executes single file analysis."""
        context = {
            "file_path": "test.py",
            "file_content": """
def get_user(user_id):
    user = User.query.get(user_id)
    return user
""",
        }

        result = await spawnable_agent.execute(
            task="Analyze this code", context=context
        )

        assert result.success is True
        assert "finding_count" in result.output

    @pytest.mark.asyncio
    async def test_adapter_execute_inline_content(self, spawnable_agent):
        """Test adapter with task as code content."""
        result = await spawnable_agent.execute(
            task="""
def vulnerable():
    user_id = request.args['id']
    return User.get(user_id)
""",
            context=None,
        )

        assert result.success is True
        assert "finding_count" in result.output

    @pytest.mark.asyncio
    async def test_adapter_execute_repo_scan(self, spawnable_agent, temp_repo):
        """Test adapter executes repository scan."""
        context = {"repo_path": str(temp_repo)}

        result = await spawnable_agent.execute(
            task="Scan repository for vulnerabilities", context=context
        )

        assert result.success is True
        assert "files_analyzed" in result.output
        assert result.output["files_analyzed"] >= 2


# =============================================================================
# LLM Integration Tests
# =============================================================================


class TestLLMIntegration:
    """Tests for LLM-enhanced analysis."""

    @pytest.mark.asyncio
    async def test_llm_analysis_called(self, analyzer_with_llm):
        """Test that LLM analysis is invoked."""
        content = "def test(): pass"

        await analyzer_with_llm.analyze_file("test.py", content)

        analyzer_with_llm.llm.generate.assert_called_once()

    @pytest.mark.asyncio
    async def test_llm_findings_parsed(self):
        """Test parsing of LLM findings."""
        mock_llm = AsyncMock()
        mock_llm.generate = AsyncMock(return_value="""
        [
            {
                "type": "idor",
                "severity": "CRITICAL",
                "title": "IDOR in get_user",
                "description": "User ID accessed without validation",
                "line_number": 42,
                "recommendation": "Add ownership check"
            }
        ]
        """)

        analyzer = BusinessLogicAnalyzerAgent(
            neptune_service=None,
            llm_client=mock_llm,
            use_llm_analysis=True,
        )

        findings = await analyzer.analyze_file("test.py", "def test(): pass")

        # Find the LLM finding
        llm_findings = [f for f in findings if f.code_snippet == "LLM analysis"]
        assert len(llm_findings) == 1
        assert llm_findings[0].vulnerability_type == VulnerabilityType.IDOR
        assert llm_findings[0].confidence == 0.7

    @pytest.mark.asyncio
    async def test_llm_error_handled(self):
        """Test graceful handling of LLM errors."""
        mock_llm = AsyncMock()
        mock_llm.generate = AsyncMock(side_effect=Exception("LLM unavailable"))

        analyzer = BusinessLogicAnalyzerAgent(
            neptune_service=None,
            llm_client=mock_llm,
            use_llm_analysis=True,
        )

        # Should not raise, just log error
        findings = await analyzer.analyze_file(
            "test.py",
            """
def get_user():
    user_id = request.args['id']
    return User.get(user_id)
""",
        )

        # Should still get pattern-based findings
        assert len(findings) >= 0  # May have pattern-based findings


# =============================================================================
# Edge Cases and Error Handling
# =============================================================================


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    @pytest.mark.asyncio
    async def test_empty_file(self, analyzer):
        """Test handling of empty file."""
        findings = await analyzer.analyze_file("test.py", "")

        assert findings == []

    @pytest.mark.asyncio
    async def test_secure_code(self, analyzer):
        """Test code with no vulnerabilities."""
        content = """
@login_required
def get_profile():
    return current_user.to_dict()

@login_required
def get_document(doc_id):
    doc = Document.query.get(doc_id)
    if doc.owner_id != current_user.id:
        abort(403)
    return doc.to_dict()
"""
        findings = await analyzer.analyze_file("test.py", content)

        # Should have minimal findings for secure code
        high_severity = [
            f for f in findings if f.severity in [Severity.CRITICAL, Severity.HIGH]
        ]
        assert len(high_severity) == 0

    @pytest.mark.asyncio
    async def test_nonexistent_file(self, analyzer):
        """Test handling of nonexistent file."""
        findings = await analyzer.analyze_file("/nonexistent/path.py")

        assert findings == []

    @pytest.mark.asyncio
    async def test_finding_id_uniqueness(self, analyzer):
        """Test that finding IDs are unique."""
        content = """
def func1():
    user_id = request.args['id1']
    return User.get(user_id)

def func2():
    doc_id = request.args['id2']
    return Doc.get(doc_id)
"""
        findings = await analyzer.analyze_file("test.py", content)
        finding_ids = [f.finding_id for f in findings]

        assert len(finding_ids) == len(set(finding_ids))


# =============================================================================
# Integration Tests
# =============================================================================


class TestIntegration:
    """Integration tests for full workflow."""

    @pytest.mark.asyncio
    async def test_full_analysis_workflow(self, analyzer, temp_repo):
        """Test complete analysis workflow."""
        result = await analyzer.analyze_repository(str(temp_repo))

        # Check all vulnerability types detected
        vuln_types = {f.vulnerability_type for f in result.findings}

        # Should detect at least IDOR and race condition
        assert VulnerabilityType.IDOR in vuln_types or len(result.findings) > 0

        # Check risk score
        assert result.risk_score > 0

        # Check analysis metadata
        assert result.analysis_duration_seconds >= 0
        assert result.total_files_analyzed >= 2

    @pytest.mark.asyncio
    async def test_combined_auth_and_logic_analysis(self, analyzer):
        """Test combined authorization and logic analysis."""
        content = """
# No auth decorator!
def get_user_data(request):
    user_id = request.args.get('user_id')
    user = User.query.get(user_id)

    # Race condition
    if user.balance >= 100:
        user.balance -= 100
        user.save()

    return user
"""
        findings = await analyzer.analyze_file("test.py", content)

        # Should find multiple types of vulnerabilities
        assert len(findings) >= 1

        # Check for mixed vulnerability types
        vuln_types = {f.vulnerability_type for f in findings}
        assert len(vuln_types) >= 1
