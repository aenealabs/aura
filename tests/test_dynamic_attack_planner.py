"""
Tests for Dynamic Attack Planner Service

Tests for penetration testing and attack surface analysis.
"""

from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

# ==================== Enum Tests ====================


class TestAttackPhase:
    """Tests for AttackPhase enum."""

    def test_all_phases(self):
        """Test all MITRE ATT&CK phases exist."""
        from src.services.security.dynamic_attack_planner import AttackPhase

        assert AttackPhase.RECONNAISSANCE == "reconnaissance"
        assert AttackPhase.RESOURCE_DEVELOPMENT == "resource_development"
        assert AttackPhase.INITIAL_ACCESS == "initial_access"
        assert AttackPhase.EXECUTION == "execution"
        assert AttackPhase.PERSISTENCE == "persistence"
        assert AttackPhase.PRIVILEGE_ESCALATION == "privilege_escalation"
        assert AttackPhase.DEFENSE_EVASION == "defense_evasion"
        assert AttackPhase.CREDENTIAL_ACCESS == "credential_access"
        assert AttackPhase.DISCOVERY == "discovery"
        assert AttackPhase.LATERAL_MOVEMENT == "lateral_movement"
        assert AttackPhase.COLLECTION == "collection"
        assert AttackPhase.COMMAND_AND_CONTROL == "command_and_control"
        assert AttackPhase.EXFILTRATION == "exfiltration"
        assert AttackPhase.IMPACT == "impact"


class TestRiskLevel:
    """Tests for RiskLevel enum."""

    def test_all_levels(self):
        """Test all risk levels exist."""
        from src.services.security.dynamic_attack_planner import RiskLevel

        assert RiskLevel.CRITICAL == "critical"
        assert RiskLevel.HIGH == "high"
        assert RiskLevel.MEDIUM == "medium"
        assert RiskLevel.LOW == "low"
        assert RiskLevel.INFO == "info"


class TestAssetType:
    """Tests for AssetType enum."""

    def test_all_types(self):
        """Test all asset types exist."""
        from src.services.security.dynamic_attack_planner import AssetType

        assert AssetType.WEB_APPLICATION == "web_application"
        assert AssetType.API_ENDPOINT == "api_endpoint"
        assert AssetType.DATABASE == "database"
        assert AssetType.STORAGE == "storage"
        assert AssetType.COMPUTE == "compute"
        assert AssetType.NETWORK == "network"
        assert AssetType.IDENTITY == "identity"
        assert AssetType.SECRETS == "secrets"
        assert AssetType.CONTAINER == "container"
        assert AssetType.SERVERLESS == "serverless"


class TestExploitDifficulty:
    """Tests for ExploitDifficulty enum."""

    def test_all_difficulties(self):
        """Test all exploit difficulties exist."""
        from src.services.security.dynamic_attack_planner import ExploitDifficulty

        assert ExploitDifficulty.TRIVIAL == "trivial"
        assert ExploitDifficulty.EASY == "easy"
        assert ExploitDifficulty.MODERATE == "moderate"
        assert ExploitDifficulty.DIFFICULT == "difficult"
        assert ExploitDifficulty.EXPERT == "expert"


class TestAttackStatus:
    """Tests for AttackStatus enum."""

    def test_all_statuses(self):
        """Test all attack statuses exist."""
        from src.services.security.dynamic_attack_planner import AttackStatus

        assert AttackStatus.PLANNED == "planned"
        assert AttackStatus.IN_PROGRESS == "in_progress"
        assert AttackStatus.COMPLETED == "completed"
        assert AttackStatus.BLOCKED == "blocked"
        assert AttackStatus.FAILED == "failed"


# ==================== Dataclass Tests ====================


class TestMITRETechnique:
    """Tests for MITRETechnique dataclass."""

    def test_creation(self):
        """Test MITRETechnique creation."""
        from src.services.security.dynamic_attack_planner import (
            AttackPhase,
            MITRETechnique,
        )

        technique = MITRETechnique(
            technique_id="T1190",
            name="Exploit Public-Facing Application",
            description="Adversaries may attempt to exploit a weakness",
            phase=AttackPhase.INITIAL_ACCESS,
            platforms=["Linux", "Windows", "macOS"],
            data_sources=["Application Log", "Network Traffic"],
            mitigations=["M1048", "M1050"],
            url="https://attack.mitre.org/techniques/T1190/",
        )
        assert technique.technique_id == "T1190"
        assert technique.phase == AttackPhase.INITIAL_ACCESS


class TestAsset:
    """Tests for Asset dataclass."""

    def test_creation(self):
        """Test Asset creation."""
        from src.services.security.dynamic_attack_planner import (
            Asset,
            AssetType,
            RiskLevel,
        )

        asset = Asset(
            asset_id="asset-001",
            name="Production API",
            asset_type=AssetType.API_ENDPOINT,
            description="Main production API endpoint",
            exposure="internet",
            technology_stack=["Python", "FastAPI", "PostgreSQL"],
            ports=[443, 8443],
            endpoints=["/api/v1", "/api/v2"],
            data_classification="confidential",
            criticality=RiskLevel.HIGH,
        )
        assert asset.asset_id == "asset-001"
        assert asset.asset_type == AssetType.API_ENDPOINT
        assert asset.criticality == RiskLevel.HIGH


class TestVulnerability:
    """Tests for Vulnerability dataclass."""

    def test_creation(self):
        """Test Vulnerability creation."""
        from src.services.security.dynamic_attack_planner import (
            RiskLevel,
            Vulnerability,
        )

        vuln = Vulnerability(
            vuln_id="vuln-001",
            cve_id="CVE-2024-12345",
            title="SQL Injection in Login",
            description="SQL injection vulnerability in login form",
            severity=RiskLevel.CRITICAL,
            cvss_score=9.8,
            affected_asset="asset-001",
            attack_vector="Network",
            exploit_available=True,
            exploit_maturity="functional",
            remediation="Use parameterized queries",
        )
        assert vuln.cve_id == "CVE-2024-12345"
        assert vuln.cvss_score == 9.8
        assert vuln.exploit_available is True


class TestAttackVector:
    """Tests for AttackVector dataclass."""

    def test_creation(self):
        """Test AttackVector creation."""
        from src.services.security.dynamic_attack_planner import (
            AttackPhase,
            AttackVector,
            ExploitDifficulty,
            MITRETechnique,
            RiskLevel,
        )

        technique = MITRETechnique(
            technique_id="T1190",
            name="Exploit Public-Facing Application",
            description="Exploit vulnerability",
            phase=AttackPhase.INITIAL_ACCESS,
            platforms=["Linux"],
            data_sources=[],
            mitigations=[],
            url="https://attack.mitre.org/techniques/T1190/",
        )
        vector = AttackVector(
            vector_id="vector-001",
            name="SQL Injection via Login",
            description="Exploit SQL injection in login form",
            entry_point="asset-001",
            target="asset-002",
            technique=technique,
            prerequisites=["Network access"],
            difficulty=ExploitDifficulty.EASY,
            impact=RiskLevel.CRITICAL,
            stealth_level="noisy",
            detection_risk=0.8,
            success_probability=0.9,
        )
        assert vector.vector_id == "vector-001"
        assert vector.difficulty == ExploitDifficulty.EASY


class TestAttackStep:
    """Tests for AttackStep dataclass."""

    def test_creation(self):
        """Test AttackStep creation."""
        from src.services.security.dynamic_attack_planner import (
            AttackPhase,
            AttackStep,
            AttackVector,
            ExploitDifficulty,
            MITRETechnique,
            RiskLevel,
        )

        technique = MITRETechnique(
            technique_id="T1110",
            name="Brute Force",
            description="Brute force attack",
            phase=AttackPhase.CREDENTIAL_ACCESS,
            platforms=["Linux"],
            data_sources=[],
            mitigations=[],
            url="https://attack.mitre.org/techniques/T1110/",
        )
        vector = AttackVector(
            vector_id="vector-001",
            name="Password Spray",
            description="Password spray attack",
            entry_point="asset-001",
            target="asset-002",
            technique=technique,
            prerequisites=[],
            difficulty=ExploitDifficulty.MODERATE,
            impact=RiskLevel.HIGH,
            stealth_level="moderate",
            detection_risk=0.5,
            success_probability=0.3,
        )
        step = AttackStep(
            step_number=1,
            name="Initial Access",
            description="Gain initial access via password spray",
            vector=vector,
            source_asset="internet",
            target_asset="asset-001",
            technique_id="T1110",
        )
        assert step.step_number == 1
        assert step.prerequisites_met is True


class TestAttackSimulation:
    """Tests for AttackSimulation dataclass."""

    def test_creation(self):
        """Test AttackSimulation creation."""
        from src.services.security.dynamic_attack_planner import (
            Asset,
            AssetType,
            AttackPath,
            AttackSimulation,
            AttackStatus,
            ExploitDifficulty,
            RiskLevel,
        )

        asset = Asset(
            asset_id="asset-001",
            name="Entry Point",
            asset_type=AssetType.WEB_APPLICATION,
            description="Web app",
            exposure="internet",
            technology_stack=["Python"],
        )
        path = AttackPath(
            path_id="path-001",
            name="Web to Database",
            description="Attack path from web to database",
            entry_point=asset,
            objective="Access database",
            steps=[],
            total_difficulty=ExploitDifficulty.MODERATE,
            total_impact=RiskLevel.CRITICAL,
            estimated_time="2 hours",
            detection_probability=0.6,
            success_probability=0.7,
            mitre_techniques=["T1190", "T1078"],
        )
        simulation = AttackSimulation(
            simulation_id="sim-001",
            attack_path=path,
            status=AttackStatus.COMPLETED,
            started_at=datetime.now(timezone.utc),
            steps_completed=5,
            steps_blocked=1,
            controls_triggered=["WAF", "IDS"],
        )
        assert simulation.simulation_id == "sim-001"
        assert simulation.status == AttackStatus.COMPLETED


class TestAttackSurface:
    """Tests for AttackSurface dataclass."""

    def test_creation(self):
        """Test AttackSurface creation."""
        from src.services.security.dynamic_attack_planner import AttackSurface

        surface = AttackSurface(
            surface_id="surface-001",
            name="Production Environment",
            scope="All production assets",
            assets=[],
            vulnerabilities=[],
            attack_vectors=[],
            attack_paths=[],
            risk_score=75.5,
        )
        assert surface.surface_id == "surface-001"
        assert surface.risk_score == 75.5


class TestThreatActor:
    """Tests for ThreatActor dataclass."""

    def test_creation(self):
        """Test ThreatActor creation."""
        from src.services.security.dynamic_attack_planner import ThreatActor

        actor = ThreatActor(
            actor_id="actor-001",
            name="Cybercrime Group",
            description="Financially motivated cybercrime group",
            motivation="financial",
            capability="medium",
            resources="moderate",
            typical_techniques=["T1566", "T1190", "T1486"],
            target_industries=["finance", "healthcare"],
        )
        assert actor.actor_id == "actor-001"
        assert actor.motivation == "financial"


class TestAttackScenario:
    """Tests for AttackScenario dataclass."""

    def test_creation(self):
        """Test AttackScenario creation."""
        from src.services.security.dynamic_attack_planner import (
            AttackScenario,
            RiskLevel,
        )

        scenario = AttackScenario(
            scenario_id="scenario-001",
            name="Ransomware Attack",
            description="Ransomware deployment via phishing",
            threat_actor="actor-001",
            objective="Encrypt data and demand ransom",
            attack_paths=["path-001", "path-002"],
            likelihood=RiskLevel.MEDIUM,
            impact=RiskLevel.CRITICAL,
            risk_rating="high",
        )
        assert scenario.scenario_id == "scenario-001"
        assert scenario.likelihood == RiskLevel.MEDIUM


class TestThreatModel:
    """Tests for ThreatModel dataclass."""

    def test_creation(self):
        """Test ThreatModel creation."""
        from src.services.security.dynamic_attack_planner import ThreatModel

        model = ThreatModel(
            model_id="model-001",
            name="Production Threat Model",
            threat_actors=[],
            attack_scenarios=[],
            crown_jewels=[],
            trust_boundaries=[],
            data_flows=[],
            assumptions=["Perimeter firewall is in place"],
        )
        assert model.model_id == "model-001"
        assert len(model.assumptions) == 1


# ==================== Planner Class Tests ====================


class TestDynamicAttackPlannerInit:
    """Tests for DynamicAttackPlanner initialization."""

    def test_basic_initialization(self):
        """Test basic initialization without clients."""
        from src.services.security.dynamic_attack_planner import DynamicAttackPlanner

        planner = DynamicAttackPlanner()
        assert planner._neptune is None
        assert planner._opensearch is None
        assert planner._llm is None
        assert planner._vuln_scanner is None

    def test_initialization_with_clients(self):
        """Test initialization with client mocks."""
        from src.services.security.dynamic_attack_planner import DynamicAttackPlanner

        neptune = MagicMock()
        opensearch = MagicMock()
        llm = MagicMock()
        vuln_scanner = MagicMock()

        planner = DynamicAttackPlanner(
            neptune_client=neptune,
            opensearch_client=opensearch,
            llm_client=llm,
            vuln_scanner=vuln_scanner,
        )
        assert planner._neptune == neptune
        assert planner._opensearch == opensearch
        assert planner._llm == llm
        assert planner._vuln_scanner == vuln_scanner

    def test_techniques_loaded(self):
        """Test MITRE techniques are loaded on init."""
        from src.services.security.dynamic_attack_planner import DynamicAttackPlanner

        planner = DynamicAttackPlanner()
        assert len(planner._techniques) > 0

    def test_threat_actors_loaded(self):
        """Test threat actor profiles are loaded on init."""
        from src.services.security.dynamic_attack_planner import DynamicAttackPlanner

        planner = DynamicAttackPlanner()
        assert len(planner._threat_actors) > 0


class TestAttackSurfaceAnalysis:
    """Tests for attack surface analysis."""

    @pytest.mark.asyncio
    async def test_analyze_empty_surface(self):
        """Test analyzing empty attack surface."""
        from src.services.security.dynamic_attack_planner import DynamicAttackPlanner

        planner = DynamicAttackPlanner()

        result = await planner.analyze_attack_surface(
            scope_name="Empty Scope", assets=[], include_vulnerability_scan=False
        )

        assert result is not None
        assert result.name == "Empty Scope"
        assert len(result.assets) == 0

    @pytest.mark.asyncio
    async def test_analyze_with_assets(self):
        """Test analyzing with assets."""
        from src.services.security.dynamic_attack_planner import (
            Asset,
            AssetType,
            DynamicAttackPlanner,
        )

        planner = DynamicAttackPlanner()

        asset = Asset(
            asset_id="asset-001",
            name="Test API",
            asset_type=AssetType.API_ENDPOINT,
            description="Test endpoint",
            exposure="internet",
            technology_stack=["Python"],
        )

        result = await planner.analyze_attack_surface(
            scope_name="Test Scope", assets=[asset], include_vulnerability_scan=False
        )

        assert result is not None
        assert len(result.assets) == 1


# ==================== Built-in Data Tests ====================


class TestBuiltInData:
    """Tests for built-in techniques and profiles."""

    def test_mitre_techniques_exist(self):
        """Test MITRE techniques are defined."""
        from src.services.security.dynamic_attack_planner import MITRE_TECHNIQUES

        assert len(MITRE_TECHNIQUES) > 0
        # Check first technique has required fields
        first_technique = list(MITRE_TECHNIQUES.values())[0]
        assert hasattr(first_technique, "technique_id")
        assert hasattr(first_technique, "name")

    def test_threat_actor_profiles_exist(self):
        """Test threat actor profiles are defined."""
        from src.services.security.dynamic_attack_planner import THREAT_ACTOR_PROFILES

        assert len(THREAT_ACTOR_PROFILES) > 0


# ==================== Edge Cases ====================


class TestEdgeCases:
    """Tests for edge cases."""

    def test_asset_with_default_values(self):
        """Test asset creation with default values."""
        from src.services.security.dynamic_attack_planner import (
            Asset,
            AssetType,
            RiskLevel,
        )

        asset = Asset(
            asset_id="asset-001",
            name="Minimal Asset",
            asset_type=AssetType.COMPUTE,
            description="Test",
            exposure="internal",
            technology_stack=[],
        )
        assert asset.data_classification == "internal"
        assert asset.criticality == RiskLevel.MEDIUM
        assert len(asset.ports) == 0

    def test_vulnerability_without_cve(self):
        """Test vulnerability without CVE ID."""
        from src.services.security.dynamic_attack_planner import (
            RiskLevel,
            Vulnerability,
        )

        vuln = Vulnerability(
            vuln_id="vuln-001",
            cve_id=None,
            title="Custom Vulnerability",
            description="Internal finding",
            severity=RiskLevel.MEDIUM,
            cvss_score=None,
            affected_asset="asset-001",
            attack_vector="Local",
        )
        assert vuln.cve_id is None
        assert vuln.cvss_score is None

    def test_attack_path_empty_steps(self):
        """Test attack path with no steps."""
        from src.services.security.dynamic_attack_planner import (
            Asset,
            AssetType,
            AttackPath,
            ExploitDifficulty,
            RiskLevel,
        )

        asset = Asset(
            asset_id="asset-001",
            name="Entry",
            asset_type=AssetType.WEB_APPLICATION,
            description="Test",
            exposure="internet",
            technology_stack=[],
        )
        path = AttackPath(
            path_id="path-001",
            name="Empty Path",
            description="Path with no steps",
            entry_point=asset,
            objective="Test",
            steps=[],
            total_difficulty=ExploitDifficulty.TRIVIAL,
            total_impact=RiskLevel.LOW,
            estimated_time="0 minutes",
            detection_probability=0.0,
            success_probability=0.0,
            mitre_techniques=[],
        )
        assert len(path.steps) == 0
        assert len(path.mitre_techniques) == 0

    def test_simulation_with_controls_triggered(self):
        """Test simulation with multiple controls triggered."""
        from src.services.security.dynamic_attack_planner import (
            Asset,
            AssetType,
            AttackPath,
            AttackSimulation,
            AttackStatus,
            ExploitDifficulty,
            RiskLevel,
        )

        asset = Asset(
            asset_id="a-001",
            name="Entry",
            asset_type=AssetType.WEB_APPLICATION,
            description="Test",
            exposure="internet",
            technology_stack=[],
        )
        path = AttackPath(
            path_id="p-001",
            name="Test Path",
            description="Test",
            entry_point=asset,
            objective="Test",
            steps=[],
            total_difficulty=ExploitDifficulty.MODERATE,
            total_impact=RiskLevel.MEDIUM,
            estimated_time="1 hour",
            detection_probability=0.5,
            success_probability=0.5,
            mitre_techniques=[],
        )
        simulation = AttackSimulation(
            simulation_id="sim-001",
            attack_path=path,
            status=AttackStatus.BLOCKED,
            started_at=datetime.now(timezone.utc),
            steps_completed=2,
            steps_blocked=3,
            controls_triggered=["WAF", "IDS", "SIEM", "EDR"],
            findings=["Vulnerability exploited", "Lateral movement detected"],
        )
        assert len(simulation.controls_triggered) == 4
        assert len(simulation.findings) == 2
