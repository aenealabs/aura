"""
Dynamic Attack Planner Service - AWS Security Agent Parity

Implements intelligent penetration testing capabilities with:
- Attack surface analysis and mapping
- MITRE ATT&CK framework integration
- Automated exploit path discovery
- Risk-prioritized attack planning
- Safe exploitation simulation
- Remediation guidance generation

Reference: ADR-030 Section 5.2 Security Agent Components
"""

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


# =============================================================================
# Enums and Constants
# =============================================================================


class AttackPhase(str, Enum):
    """MITRE ATT&CK kill chain phases."""

    RECONNAISSANCE = "reconnaissance"
    RESOURCE_DEVELOPMENT = "resource_development"
    INITIAL_ACCESS = "initial_access"
    EXECUTION = "execution"
    PERSISTENCE = "persistence"
    PRIVILEGE_ESCALATION = "privilege_escalation"
    DEFENSE_EVASION = "defense_evasion"
    CREDENTIAL_ACCESS = "credential_access"
    DISCOVERY = "discovery"
    LATERAL_MOVEMENT = "lateral_movement"
    COLLECTION = "collection"
    COMMAND_AND_CONTROL = "command_and_control"
    EXFILTRATION = "exfiltration"
    IMPACT = "impact"


class RiskLevel(str, Enum):
    """Risk assessment levels."""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class AssetType(str, Enum):
    """Types of assets in attack surface."""

    WEB_APPLICATION = "web_application"
    API_ENDPOINT = "api_endpoint"
    DATABASE = "database"
    STORAGE = "storage"
    COMPUTE = "compute"
    NETWORK = "network"
    IDENTITY = "identity"
    SECRETS = "secrets"
    CONTAINER = "container"
    SERVERLESS = "serverless"


class ExploitDifficulty(str, Enum):
    """Difficulty level of exploitation."""

    TRIVIAL = "trivial"  # Script kiddie level
    EASY = "easy"  # Basic skills required
    MODERATE = "moderate"  # Intermediate skills
    DIFFICULT = "difficult"  # Advanced skills
    EXPERT = "expert"  # Nation-state level


class AttackStatus(str, Enum):
    """Status of attack simulation."""

    PLANNED = "planned"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    BLOCKED = "blocked"
    FAILED = "failed"


# =============================================================================
# Data Models
# =============================================================================


@dataclass
class MITRETechnique:
    """MITRE ATT&CK technique reference."""

    technique_id: str  # e.g., T1190
    name: str
    description: str
    phase: AttackPhase
    platforms: list[str]  # Windows, Linux, macOS, Cloud
    data_sources: list[str]  # Detection data sources
    mitigations: list[str]  # Mitigation IDs
    url: str


@dataclass
class Asset:
    """An asset in the attack surface."""

    asset_id: str
    name: str
    asset_type: AssetType
    description: str
    exposure: str  # internet, internal, restricted
    technology_stack: list[str]
    ports: list[int] = field(default_factory=list)
    endpoints: list[str] = field(default_factory=list)
    data_classification: str = "internal"
    criticality: RiskLevel = RiskLevel.MEDIUM
    owner: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class Vulnerability:
    """A discovered vulnerability."""

    vuln_id: str
    cve_id: str | None
    title: str
    description: str
    severity: RiskLevel
    cvss_score: float | None
    affected_asset: str  # Asset ID
    attack_vector: str
    exploit_available: bool = False
    exploit_maturity: str = "unproven"  # unproven, poc, functional, high
    remediation: str = ""
    references: list[str] = field(default_factory=list)


@dataclass
class AttackVector:
    """A potential attack vector."""

    vector_id: str
    name: str
    description: str
    entry_point: str  # Asset ID
    target: str  # Asset ID
    technique: MITRETechnique
    prerequisites: list[str]  # Required conditions
    difficulty: ExploitDifficulty
    impact: RiskLevel
    stealth_level: str  # noisy, moderate, stealthy
    detection_risk: float  # 0.0-1.0
    success_probability: float  # 0.0-1.0


@dataclass
class AttackPath:
    """A complete attack path from entry to objective."""

    path_id: str
    name: str
    description: str
    entry_point: Asset
    objective: str  # What the attacker achieves
    steps: list["AttackStep"]
    total_difficulty: ExploitDifficulty
    total_impact: RiskLevel
    estimated_time: str  # Human-readable duration
    detection_probability: float
    success_probability: float
    mitre_techniques: list[str]


@dataclass
class AttackStep:
    """A single step in an attack path."""

    step_number: int
    name: str
    description: str
    vector: AttackVector
    source_asset: str
    target_asset: str
    technique_id: str
    prerequisites_met: bool = True
    execution_notes: str = ""
    artifacts_created: list[str] = field(default_factory=list)


@dataclass
class AttackSimulation:
    """Result of a simulated attack."""

    simulation_id: str
    attack_path: AttackPath
    status: AttackStatus
    started_at: datetime
    completed_at: datetime | None = None
    steps_completed: int = 0
    steps_blocked: int = 0
    controls_triggered: list[str] = field(default_factory=list)
    evidence_collected: list[dict] = field(default_factory=list)
    findings: list[str] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)


@dataclass
class AttackSurface:
    """Complete attack surface analysis."""

    surface_id: str
    name: str
    scope: str
    assets: list[Asset]
    vulnerabilities: list[Vulnerability]
    attack_vectors: list[AttackVector]
    attack_paths: list[AttackPath]
    risk_score: float
    analyzed_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class ThreatModel:
    """Threat model for the target environment."""

    model_id: str
    name: str
    threat_actors: list["ThreatActor"]
    attack_scenarios: list["AttackScenario"]
    crown_jewels: list[Asset]  # High-value targets
    trust_boundaries: list[dict]
    data_flows: list[dict]
    assumptions: list[str]
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class ThreatActor:
    """Profile of a potential threat actor."""

    actor_id: str
    name: str
    description: str
    motivation: str  # financial, espionage, hacktivism, etc.
    capability: str  # low, medium, high, nation-state
    resources: str  # limited, moderate, extensive
    typical_techniques: list[str]  # MITRE technique IDs
    target_industries: list[str]


@dataclass
class AttackScenario:
    """A specific attack scenario to test."""

    scenario_id: str
    name: str
    description: str
    threat_actor: str  # Actor ID
    objective: str
    attack_paths: list[str]  # Path IDs
    likelihood: RiskLevel
    impact: RiskLevel
    risk_rating: str  # Combined likelihood x impact


@dataclass
class RemediationPlan:
    """Remediation plan for discovered risks."""

    plan_id: str
    title: str
    findings: list[str]  # Finding IDs addressed
    priority: RiskLevel
    effort_estimate: str  # hours/days/weeks
    steps: list["RemediationStep"]
    expected_risk_reduction: float
    verification_steps: list[str]


@dataclass
class RemediationStep:
    """A single remediation step."""

    step_number: int
    action: str
    description: str
    responsible_team: str
    resources_needed: list[str]
    verification: str


# =============================================================================
# MITRE ATT&CK Knowledge Base
# =============================================================================

MITRE_TECHNIQUES = {
    # Initial Access
    "T1190": MITRETechnique(
        technique_id="T1190",
        name="Exploit Public-Facing Application",
        description="Adversaries may attempt to exploit a weakness in an Internet-facing host or system",
        phase=AttackPhase.INITIAL_ACCESS,
        platforms=["Linux", "Windows", "macOS", "Containers", "Cloud"],
        data_sources=["Application Log", "Network Traffic"],
        mitigations=["M1048", "M1050", "M1051"],
        url="https://attack.mitre.org/techniques/T1190",
    ),
    "T1133": MITRETechnique(
        technique_id="T1133",
        name="External Remote Services",
        description="Adversaries may leverage external-facing remote services to initially access a network",
        phase=AttackPhase.INITIAL_ACCESS,
        platforms=["Linux", "Windows", "macOS", "Cloud"],
        data_sources=["Authentication Logs", "Network Traffic"],
        mitigations=["M1035", "M1032", "M1030"],
        url="https://attack.mitre.org/techniques/T1133",
    ),
    "T1078": MITRETechnique(
        technique_id="T1078",
        name="Valid Accounts",
        description="Adversaries may obtain and abuse credentials of existing accounts",
        phase=AttackPhase.INITIAL_ACCESS,
        platforms=["Linux", "Windows", "macOS", "Cloud", "Containers"],
        data_sources=["Authentication Logs", "User Account"],
        mitigations=["M1027", "M1026", "M1017"],
        url="https://attack.mitre.org/techniques/T1078",
    ),
    # Execution
    "T1059": MITRETechnique(
        technique_id="T1059",
        name="Command and Scripting Interpreter",
        description="Adversaries may abuse command and script interpreters to execute commands",
        phase=AttackPhase.EXECUTION,
        platforms=["Linux", "Windows", "macOS", "Cloud"],
        data_sources=["Command", "Process", "Script"],
        mitigations=["M1049", "M1038", "M1026"],
        url="https://attack.mitre.org/techniques/T1059",
    ),
    "T1203": MITRETechnique(
        technique_id="T1203",
        name="Exploitation for Client Execution",
        description="Adversaries may exploit software vulnerabilities in client applications",
        phase=AttackPhase.EXECUTION,
        platforms=["Linux", "Windows", "macOS"],
        data_sources=["Application Log", "Process"],
        mitigations=["M1050", "M1048", "M1051"],
        url="https://attack.mitre.org/techniques/T1203",
    ),
    # Privilege Escalation
    "T1068": MITRETechnique(
        technique_id="T1068",
        name="Exploitation for Privilege Escalation",
        description="Adversaries may exploit software vulnerabilities to escalate privileges",
        phase=AttackPhase.PRIVILEGE_ESCALATION,
        platforms=["Linux", "Windows", "macOS", "Containers"],
        data_sources=["Process", "Driver"],
        mitigations=["M1048", "M1050", "M1019"],
        url="https://attack.mitre.org/techniques/T1068",
    ),
    "T1548": MITRETechnique(
        technique_id="T1548",
        name="Abuse Elevation Control Mechanism",
        description="Adversaries may circumvent mechanisms designed to control elevated privileges",
        phase=AttackPhase.PRIVILEGE_ESCALATION,
        platforms=["Linux", "Windows", "macOS"],
        data_sources=["Command", "Process", "User Account"],
        mitigations=["M1047", "M1028", "M1026"],
        url="https://attack.mitre.org/techniques/T1548",
    ),
    # Credential Access
    "T1552": MITRETechnique(
        technique_id="T1552",
        name="Unsecured Credentials",
        description="Adversaries may search compromised systems for insecurely stored credentials",
        phase=AttackPhase.CREDENTIAL_ACCESS,
        platforms=["Linux", "Windows", "macOS", "Cloud", "Containers"],
        data_sources=["Command", "File", "Process"],
        mitigations=["M1027", "M1026", "M1022"],
        url="https://attack.mitre.org/techniques/T1552",
    ),
    "T1110": MITRETechnique(
        technique_id="T1110",
        name="Brute Force",
        description="Adversaries may use brute force techniques to gain access to accounts",
        phase=AttackPhase.CREDENTIAL_ACCESS,
        platforms=["Linux", "Windows", "macOS", "Cloud", "Containers"],
        data_sources=["Authentication Logs", "User Account"],
        mitigations=["M1036", "M1032", "M1027"],
        url="https://attack.mitre.org/techniques/T1110",
    ),
    # Lateral Movement
    "T1021": MITRETechnique(
        technique_id="T1021",
        name="Remote Services",
        description="Adversaries may use valid accounts to log into remote services",
        phase=AttackPhase.LATERAL_MOVEMENT,
        platforms=["Linux", "Windows", "macOS", "Cloud"],
        data_sources=["Authentication Logs", "Network Traffic"],
        mitigations=["M1032", "M1035", "M1030"],
        url="https://attack.mitre.org/techniques/T1021",
    ),
    "T1550": MITRETechnique(
        technique_id="T1550",
        name="Use Alternate Authentication Material",
        description="Adversaries may use alternate authentication material to move laterally",
        phase=AttackPhase.LATERAL_MOVEMENT,
        platforms=["Linux", "Windows", "macOS", "Cloud"],
        data_sources=["Authentication Logs", "User Account"],
        mitigations=["M1026", "M1027", "M1018"],
        url="https://attack.mitre.org/techniques/T1550",
    ),
    # Exfiltration
    "T1041": MITRETechnique(
        technique_id="T1041",
        name="Exfiltration Over C2 Channel",
        description="Adversaries may steal data by exfiltrating it over an existing C2 channel",
        phase=AttackPhase.EXFILTRATION,
        platforms=["Linux", "Windows", "macOS"],
        data_sources=["Network Traffic", "Command"],
        mitigations=["M1031", "M1057"],
        url="https://attack.mitre.org/techniques/T1041",
    ),
    "T1567": MITRETechnique(
        technique_id="T1567",
        name="Exfiltration Over Web Service",
        description="Adversaries may use an existing web service to exfiltrate data",
        phase=AttackPhase.EXFILTRATION,
        platforms=["Linux", "Windows", "macOS"],
        data_sources=["Network Traffic", "Command"],
        mitigations=["M1021", "M1057"],
        url="https://attack.mitre.org/techniques/T1567",
    ),
    # Cloud-specific
    "T1537": MITRETechnique(
        technique_id="T1537",
        name="Transfer Data to Cloud Account",
        description="Adversaries may exfiltrate data to another cloud account they control",
        phase=AttackPhase.EXFILTRATION,
        platforms=["Cloud"],
        data_sources=["Cloud Storage", "Snapshot"],
        mitigations=["M1037", "M1018"],
        url="https://attack.mitre.org/techniques/T1537",
    ),
    "T1578": MITRETechnique(
        technique_id="T1578",
        name="Modify Cloud Compute Infrastructure",
        description="Adversaries may modify cloud compute infrastructure to evade defenses",
        phase=AttackPhase.DEFENSE_EVASION,
        platforms=["Cloud"],
        data_sources=["Cloud Service", "Instance"],
        mitigations=["M1047", "M1018"],
        url="https://attack.mitre.org/techniques/T1578",
    ),
}

THREAT_ACTOR_PROFILES = {
    "apt_nation_state": ThreatActor(
        actor_id="apt_nation_state",
        name="Nation-State APT",
        description="Sophisticated state-sponsored threat actor with extensive resources",
        motivation="espionage",
        capability="nation-state",
        resources="extensive",
        typical_techniques=["T1190", "T1078", "T1068", "T1552", "T1537"],
        target_industries=["government", "defense", "energy", "technology"],
    ),
    "organized_crime": ThreatActor(
        actor_id="organized_crime",
        name="Organized Cybercrime",
        description="Financially motivated criminal group with moderate resources",
        motivation="financial",
        capability="high",
        resources="moderate",
        typical_techniques=["T1190", "T1110", "T1059", "T1041"],
        target_industries=["finance", "healthcare", "retail", "technology"],
    ),
    "insider_threat": ThreatActor(
        actor_id="insider_threat",
        name="Malicious Insider",
        description="Current or former employee with legitimate access",
        motivation="financial",
        capability="medium",
        resources="limited",
        typical_techniques=["T1078", "T1552", "T1567"],
        target_industries=["all"],
    ),
    "opportunistic": ThreatActor(
        actor_id="opportunistic",
        name="Opportunistic Attacker",
        description="Low-skill attacker exploiting known vulnerabilities",
        motivation="financial",
        capability="low",
        resources="limited",
        typical_techniques=["T1190", "T1110"],
        target_industries=["all"],
    ),
}


# =============================================================================
# Dynamic Attack Planner Service
# =============================================================================


class DynamicAttackPlanner:
    """
    Intelligent penetration testing and attack planning service.

    Provides comprehensive attack surface analysis and simulation:
    - MITRE ATT&CK framework integration
    - Automated attack path discovery
    - Risk-prioritized planning
    - Safe exploitation simulation
    - Remediation guidance
    """

    def __init__(
        self,
        neptune_client: Any = None,
        opensearch_client: Any = None,
        llm_client: Any = None,
        vuln_scanner: Any = None,
    ):
        self._neptune = neptune_client
        self._opensearch = opensearch_client
        self._llm = llm_client
        self._vuln_scanner = vuln_scanner

        self._techniques = MITRE_TECHNIQUES
        self._threat_actors = THREAT_ACTOR_PROFILES

        self._attack_surfaces: dict[str, AttackSurface] = {}
        self._simulations: dict[str, AttackSimulation] = {}

        self._logger = logger.bind(service="dynamic_attack_planner")

    # =========================================================================
    # Attack Surface Analysis
    # =========================================================================

    async def analyze_attack_surface(
        self,
        scope_name: str,
        assets: list[Asset],
        include_vulnerability_scan: bool = True,
    ) -> AttackSurface:
        """
        Perform comprehensive attack surface analysis.

        Args:
            scope_name: Name of the scope being analyzed
            assets: List of assets to analyze
            include_vulnerability_scan: Whether to scan for vulnerabilities

        Returns:
            Complete attack surface analysis
        """
        surface_id = str(uuid.uuid4())

        self._logger.info(
            "Starting attack surface analysis",
            surface_id=surface_id,
            scope=scope_name,
            asset_count=len(assets),
        )

        # Discover vulnerabilities
        vulnerabilities = []
        if include_vulnerability_scan:
            vulnerabilities = await self._discover_vulnerabilities(assets)

        # Identify attack vectors
        attack_vectors = await self._identify_attack_vectors(assets, vulnerabilities)

        # Generate attack paths
        attack_paths = await self._generate_attack_paths(assets, attack_vectors)

        # Calculate risk score
        risk_score = self._calculate_risk_score(vulnerabilities, attack_paths)

        surface = AttackSurface(
            surface_id=surface_id,
            name=scope_name,
            scope=f"Analysis of {len(assets)} assets",
            assets=assets,
            vulnerabilities=vulnerabilities,
            attack_vectors=attack_vectors,
            attack_paths=attack_paths,
            risk_score=risk_score,
        )

        self._attack_surfaces[surface_id] = surface

        self._logger.info(
            "Attack surface analysis completed",
            surface_id=surface_id,
            vulnerabilities=len(vulnerabilities),
            attack_vectors=len(attack_vectors),
            attack_paths=len(attack_paths),
            risk_score=risk_score,
        )

        return surface

    async def _discover_vulnerabilities(
        self, assets: list[Asset]
    ) -> list[Vulnerability]:
        """Discover vulnerabilities in assets."""
        vulnerabilities = []

        for asset in assets:
            # Simulate vulnerability discovery based on asset type
            asset_vulns = await self._scan_asset_vulnerabilities(asset)
            vulnerabilities.extend(asset_vulns)

        return vulnerabilities

    async def _scan_asset_vulnerabilities(self, asset: Asset) -> list[Vulnerability]:
        """Scan a single asset for vulnerabilities."""
        vulns = []

        # Technology-based vulnerability patterns
        vuln_patterns = {
            "nginx": [
                Vulnerability(
                    vuln_id=str(uuid.uuid4()),
                    cve_id="CVE-2021-23017",
                    title="nginx DNS Resolver Vulnerability",
                    description="1-byte memory overwrite in nginx resolver",
                    severity=RiskLevel.HIGH,
                    cvss_score=7.7,
                    affected_asset=asset.asset_id,
                    attack_vector="network",
                    exploit_available=True,
                    exploit_maturity="poc",
                    remediation="Upgrade nginx to version 1.21.0 or later",
                )
            ],
            "apache": [
                Vulnerability(
                    vuln_id=str(uuid.uuid4()),
                    cve_id="CVE-2021-41773",
                    title="Apache Path Traversal",
                    description="Path traversal and file disclosure vulnerability",
                    severity=RiskLevel.CRITICAL,
                    cvss_score=9.8,
                    affected_asset=asset.asset_id,
                    attack_vector="network",
                    exploit_available=True,
                    exploit_maturity="high",
                    remediation="Upgrade Apache to version 2.4.51 or later",
                )
            ],
            "kubernetes": [
                Vulnerability(
                    vuln_id=str(uuid.uuid4()),
                    cve_id="CVE-2021-25741",
                    title="Kubernetes symlink exchange",
                    description="User can create symlinks that point to arbitrary files",
                    severity=RiskLevel.HIGH,
                    cvss_score=8.8,
                    affected_asset=asset.asset_id,
                    attack_vector="local",
                    exploit_available=True,
                    exploit_maturity="functional",
                    remediation="Upgrade Kubernetes to patched version",
                )
            ],
            "postgresql": [
                Vulnerability(
                    vuln_id=str(uuid.uuid4()),
                    cve_id=None,
                    title="Weak Database Authentication",
                    description="Database accepts connections without strong authentication",
                    severity=RiskLevel.HIGH,
                    cvss_score=7.5,
                    affected_asset=asset.asset_id,
                    attack_vector="network",
                    exploit_available=False,
                    remediation="Enable SSL/TLS and require certificate authentication",
                )
            ],
        }

        # Check technology stack for known vulnerabilities
        for tech in asset.technology_stack:
            tech_lower = tech.lower()
            for pattern, pattern_vulns in vuln_patterns.items():
                if pattern in tech_lower:
                    vulns.extend(pattern_vulns)

        # Check for common misconfigurations based on asset type
        if asset.asset_type == AssetType.WEB_APPLICATION:
            if asset.exposure == "internet":
                vulns.append(
                    Vulnerability(
                        vuln_id=str(uuid.uuid4()),
                        cve_id=None,
                        title="Missing Security Headers",
                        description="Web application missing critical security headers (CSP, HSTS, X-Frame-Options)",
                        severity=RiskLevel.MEDIUM,
                        cvss_score=5.0,
                        affected_asset=asset.asset_id,
                        attack_vector="network",
                        remediation="Implement security headers: Content-Security-Policy, Strict-Transport-Security",
                    )
                )

        if asset.asset_type == AssetType.API_ENDPOINT:
            vulns.append(
                Vulnerability(
                    vuln_id=str(uuid.uuid4()),
                    cve_id=None,
                    title="API Rate Limiting Not Detected",
                    description="API endpoint may be vulnerable to brute force attacks",
                    severity=RiskLevel.MEDIUM,
                    cvss_score=5.3,
                    affected_asset=asset.asset_id,
                    attack_vector="network",
                    remediation="Implement rate limiting on all API endpoints",
                )
            )

        if asset.asset_type == AssetType.STORAGE:
            vulns.append(
                Vulnerability(
                    vuln_id=str(uuid.uuid4()),
                    cve_id=None,
                    title="Storage Access Controls Review Needed",
                    description="Storage bucket access controls should be reviewed for least privilege",
                    severity=RiskLevel.LOW,
                    cvss_score=3.0,
                    affected_asset=asset.asset_id,
                    attack_vector="network",
                    remediation="Review and restrict bucket policies to minimum required access",
                )
            )

        return vulns

    async def _identify_attack_vectors(
        self, assets: list[Asset], vulnerabilities: list[Vulnerability]
    ) -> list[AttackVector]:
        """Identify potential attack vectors."""
        vectors = []

        # Map vulnerabilities to techniques
        for vuln in vulnerabilities:
            technique = self._map_vuln_to_technique(vuln)
            if technique:
                asset = next(
                    (a for a in assets if a.asset_id == vuln.affected_asset), None
                )
                if asset:
                    vector = AttackVector(
                        vector_id=str(uuid.uuid4()),
                        name=f"Exploit {vuln.title}",
                        description=f"Leverage {vuln.cve_id or 'misconfiguration'} to compromise {asset.name}",
                        entry_point=asset.asset_id,
                        target=asset.asset_id,
                        technique=technique,
                        prerequisites=[],
                        difficulty=self._assess_exploit_difficulty(vuln),
                        impact=vuln.severity,
                        stealth_level="moderate",
                        detection_risk=0.5,
                        success_probability=0.7 if vuln.exploit_available else 0.3,
                    )
                    vectors.append(vector)

        # Add generic attack vectors based on asset exposure
        for asset in assets:
            if asset.exposure == "internet":
                # Brute force vector
                vectors.append(
                    AttackVector(
                        vector_id=str(uuid.uuid4()),
                        name=f"Brute Force {asset.name}",
                        description="Attempt credential stuffing or brute force attack",
                        entry_point=asset.asset_id,
                        target=asset.asset_id,
                        technique=self._techniques["T1110"],
                        prerequisites=["valid_usernames"],
                        difficulty=ExploitDifficulty.EASY,
                        impact=RiskLevel.HIGH,
                        stealth_level="noisy",
                        detection_risk=0.9,
                        success_probability=0.2,
                    )
                )

        return vectors

    def _map_vuln_to_technique(self, vuln: Vulnerability) -> MITRETechnique | None:
        """Map a vulnerability to MITRE ATT&CK technique."""
        if vuln.attack_vector == "network":
            if "traversal" in vuln.title.lower():
                return self._techniques.get("T1190")
            if "injection" in vuln.title.lower():
                return self._techniques.get("T1059")
            if "authentication" in vuln.title.lower():
                return self._techniques.get("T1078")
            # Default for network vulns
            return self._techniques.get("T1190")

        if vuln.attack_vector == "local":
            if "privilege" in vuln.title.lower():
                return self._techniques.get("T1068")
            return self._techniques.get("T1548")

        return self._techniques.get("T1190")  # Default

    def _assess_exploit_difficulty(self, vuln: Vulnerability) -> ExploitDifficulty:
        """Assess exploit difficulty based on vulnerability characteristics."""
        if vuln.exploit_maturity == "high":
            return ExploitDifficulty.EASY
        elif vuln.exploit_maturity == "functional":
            return ExploitDifficulty.MODERATE
        elif vuln.exploit_maturity == "poc":
            return ExploitDifficulty.MODERATE
        elif vuln.exploit_available:
            return ExploitDifficulty.MODERATE
        else:
            return ExploitDifficulty.DIFFICULT

    async def _generate_attack_paths(
        self, assets: list[Asset], vectors: list[AttackVector]
    ) -> list[AttackPath]:
        """Generate complete attack paths from entry to objective."""
        paths = []

        # Find internet-facing entry points
        entry_points = [a for a in assets if a.exposure == "internet"]

        # Find high-value targets
        crown_jewels = [
            a for a in assets if a.criticality in [RiskLevel.CRITICAL, RiskLevel.HIGH]
        ]

        # Generate paths from entry points to crown jewels
        for entry in entry_points:
            entry_vectors = [v for v in vectors if v.entry_point == entry.asset_id]

            for target in crown_jewels:
                if entry.asset_id == target.asset_id:
                    # Direct path
                    for vector in entry_vectors:
                        path = self._build_direct_path(entry, target, vector)
                        if path:
                            paths.append(path)
                else:
                    # Multi-hop path
                    path = await self._build_multi_hop_path(
                        entry, target, assets, vectors
                    )
                    if path:
                        paths.append(path)

        # Sort by risk (success probability * impact)
        paths.sort(
            key=lambda p: p.success_probability * self._risk_to_score(p.total_impact),
            reverse=True,
        )

        return paths[:20]  # Return top 20 paths

    def _build_direct_path(
        self, entry: Asset, target: Asset, vector: AttackVector
    ) -> AttackPath | None:
        """Build a direct attack path."""
        step = AttackStep(
            step_number=1,
            name=vector.name,
            description=vector.description,
            vector=vector,
            source_asset="external",
            target_asset=target.asset_id,
            technique_id=vector.technique.technique_id,
        )

        return AttackPath(
            path_id=str(uuid.uuid4()),
            name=f"Direct attack on {target.name}",
            description=f"Exploit {vector.name} to compromise {target.name}",
            entry_point=entry,
            objective=f"Compromise {target.name}",
            steps=[step],
            total_difficulty=vector.difficulty,
            total_impact=vector.impact,
            estimated_time=self._estimate_attack_time(vector.difficulty),
            detection_probability=vector.detection_risk,
            success_probability=vector.success_probability,
            mitre_techniques=[vector.technique.technique_id],
        )

    async def _build_multi_hop_path(
        self,
        entry: Asset,
        target: Asset,
        assets: list[Asset],
        vectors: list[AttackVector],
    ) -> AttackPath | None:
        """Build a multi-hop attack path."""
        # Simplified path building - find intermediate hops
        steps = []
        _current = entry  # noqa: F841
        techniques = []

        # Step 1: Initial access
        entry_vectors = [v for v in vectors if v.entry_point == entry.asset_id]
        if not entry_vectors:
            return None

        initial_vector = entry_vectors[0]
        steps.append(
            AttackStep(
                step_number=1,
                name=f"Initial Access via {initial_vector.name}",
                description=f"Gain foothold on {entry.name}",
                vector=initial_vector,
                source_asset="external",
                target_asset=entry.asset_id,
                technique_id=initial_vector.technique.technique_id,
            )
        )
        techniques.append(initial_vector.technique.technique_id)

        # Step 2: Credential harvesting (simulated)
        cred_technique = self._techniques.get("T1552")
        if cred_technique:
            steps.append(
                AttackStep(
                    step_number=2,
                    name="Credential Harvesting",
                    description="Search for credentials on compromised system",
                    vector=AttackVector(
                        vector_id=str(uuid.uuid4()),
                        name="Credential Search",
                        description="Search for stored credentials",
                        entry_point=entry.asset_id,
                        target=entry.asset_id,
                        technique=cred_technique,
                        prerequisites=["initial_access"],
                        difficulty=ExploitDifficulty.EASY,
                        impact=RiskLevel.HIGH,
                        stealth_level="stealthy",
                        detection_risk=0.3,
                        success_probability=0.6,
                    ),
                    source_asset=entry.asset_id,
                    target_asset=entry.asset_id,
                    technique_id="T1552",
                )
            )
            techniques.append("T1552")

        # Step 3: Lateral movement
        lateral_technique = self._techniques.get("T1021")
        if lateral_technique:
            steps.append(
                AttackStep(
                    step_number=3,
                    name=f"Lateral Movement to {target.name}",
                    description=f"Use harvested credentials to access {target.name}",
                    vector=AttackVector(
                        vector_id=str(uuid.uuid4()),
                        name="Lateral Movement",
                        description="Move laterally to target",
                        entry_point=entry.asset_id,
                        target=target.asset_id,
                        technique=lateral_technique,
                        prerequisites=["credentials"],
                        difficulty=ExploitDifficulty.MODERATE,
                        impact=RiskLevel.HIGH,
                        stealth_level="moderate",
                        detection_risk=0.5,
                        success_probability=0.5,
                    ),
                    source_asset=entry.asset_id,
                    target_asset=target.asset_id,
                    technique_id="T1021",
                )
            )
            techniques.append("T1021")

        # Calculate overall metrics
        total_success = 1.0
        total_detection = 0.0
        max_difficulty = ExploitDifficulty.EASY

        for step in steps:
            total_success *= step.vector.success_probability
            total_detection = max(total_detection, step.vector.detection_risk)
            if self._difficulty_to_score(
                step.vector.difficulty
            ) > self._difficulty_to_score(max_difficulty):
                max_difficulty = step.vector.difficulty

        return AttackPath(
            path_id=str(uuid.uuid4()),
            name=f"Multi-hop attack to {target.name}",
            description=f"Compromise {entry.name} and pivot to {target.name}",
            entry_point=entry,
            objective=f"Gain access to {target.name}",
            steps=steps,
            total_difficulty=max_difficulty,
            total_impact=RiskLevel.HIGH,
            estimated_time=self._estimate_attack_time(max_difficulty, len(steps)),
            detection_probability=total_detection,
            success_probability=total_success,
            mitre_techniques=techniques,
        )

    def _risk_to_score(self, risk: RiskLevel) -> float:
        """Convert risk level to numeric score."""
        scores = {
            RiskLevel.CRITICAL: 10.0,
            RiskLevel.HIGH: 7.5,
            RiskLevel.MEDIUM: 5.0,
            RiskLevel.LOW: 2.5,
            RiskLevel.INFO: 1.0,
        }
        return scores.get(risk, 5.0)

    def _difficulty_to_score(self, difficulty: ExploitDifficulty) -> int:
        """Convert difficulty to numeric score."""
        scores = {
            ExploitDifficulty.TRIVIAL: 1,
            ExploitDifficulty.EASY: 2,
            ExploitDifficulty.MODERATE: 3,
            ExploitDifficulty.DIFFICULT: 4,
            ExploitDifficulty.EXPERT: 5,
        }
        return scores.get(difficulty, 3)

    def _estimate_attack_time(
        self, difficulty: ExploitDifficulty, steps: int = 1
    ) -> str:
        """Estimate time to execute attack."""
        base_times = {
            ExploitDifficulty.TRIVIAL: 5,
            ExploitDifficulty.EASY: 30,
            ExploitDifficulty.MODERATE: 120,
            ExploitDifficulty.DIFFICULT: 480,
            ExploitDifficulty.EXPERT: 1440,
        }

        minutes = base_times.get(difficulty, 60) * steps

        if minutes < 60:
            return f"{minutes} minutes"
        elif minutes < 1440:
            return f"{minutes // 60} hours"
        else:
            return f"{minutes // 1440} days"

    def _calculate_risk_score(
        self, vulnerabilities: list[Vulnerability], attack_paths: list[AttackPath]
    ) -> float:
        """Calculate overall risk score (0-100)."""
        score = 0.0

        # Vulnerability contribution
        for vuln in vulnerabilities:
            if vuln.cvss_score:
                score += vuln.cvss_score * (1.5 if vuln.exploit_available else 1.0)

        # Attack path contribution
        for path in attack_paths:
            path_score = (
                path.success_probability * self._risk_to_score(path.total_impact) * 2
            )
            score += path_score

        return min(100.0, score)

    # =========================================================================
    # Threat Modeling
    # =========================================================================

    async def create_threat_model(
        self, name: str, assets: list[Asset], threat_actors: list[str] | None = None
    ) -> ThreatModel:
        """
        Create a threat model for the environment.

        Args:
            name: Name for the threat model
            assets: Assets to include in the model
            threat_actors: Specific threat actors to consider (defaults to all)

        Returns:
            Complete threat model
        """
        model_id = str(uuid.uuid4())

        # Select threat actors
        actors = []
        actor_ids = threat_actors or list(self._threat_actors.keys())
        for actor_id in actor_ids:
            if actor_id in self._threat_actors:
                actors.append(self._threat_actors[actor_id])

        # Identify crown jewels
        crown_jewels = [
            a for a in assets if a.criticality in [RiskLevel.CRITICAL, RiskLevel.HIGH]
        ]

        # Generate attack scenarios
        scenarios = await self._generate_attack_scenarios(assets, actors, crown_jewels)

        # Define trust boundaries
        trust_boundaries = self._identify_trust_boundaries(assets)

        # Map data flows
        data_flows = self._map_data_flows(assets)

        model = ThreatModel(
            model_id=model_id,
            name=name,
            threat_actors=actors,
            attack_scenarios=scenarios,
            crown_jewels=crown_jewels,
            trust_boundaries=trust_boundaries,
            data_flows=data_flows,
            assumptions=[
                "Network segmentation is properly configured",
                "Logging and monitoring are in place",
                "Incident response procedures exist",
            ],
        )

        self._logger.info(
            "Threat model created",
            model_id=model_id,
            actors=len(actors),
            scenarios=len(scenarios),
            crown_jewels=len(crown_jewels),
        )

        return model

    async def _generate_attack_scenarios(
        self, assets: list[Asset], actors: list[ThreatActor], crown_jewels: list[Asset]
    ) -> list[AttackScenario]:
        """Generate attack scenarios based on threat actors."""
        scenarios = []

        for actor in actors:
            for target in crown_jewels:
                # Match actor capabilities to target
                scenario = AttackScenario(
                    scenario_id=str(uuid.uuid4()),
                    name=f"{actor.name} targeting {target.name}",
                    description=f"Scenario where {actor.name} attempts to compromise {target.name}",
                    threat_actor=actor.actor_id,
                    objective=(
                        f"Exfiltrate data from {target.name}"
                        if actor.motivation == "espionage"
                        else f"Deploy ransomware on {target.name}"
                    ),
                    attack_paths=[],  # Would be populated with actual path IDs
                    likelihood=self._assess_scenario_likelihood(actor, target),
                    impact=target.criticality,
                    risk_rating=self._calculate_risk_rating(
                        self._assess_scenario_likelihood(actor, target),
                        target.criticality,
                    ),
                )
                scenarios.append(scenario)

        return scenarios

    def _assess_scenario_likelihood(
        self, actor: ThreatActor, target: Asset
    ) -> RiskLevel:
        """Assess likelihood of attack scenario."""
        capability_scores = {"nation-state": 4, "high": 3, "medium": 2, "low": 1}

        exposure_multiplier = {"internet": 1.5, "internal": 1.0, "restricted": 0.5}

        score = float(capability_scores.get(actor.capability, 2))
        score *= exposure_multiplier.get(target.exposure, 1.0)

        if score >= 4:
            return RiskLevel.HIGH
        elif score >= 2.5:
            return RiskLevel.MEDIUM
        else:
            return RiskLevel.LOW

    def _calculate_risk_rating(self, likelihood: RiskLevel, impact: RiskLevel) -> str:
        """Calculate combined risk rating."""
        matrix = {
            (RiskLevel.HIGH, RiskLevel.CRITICAL): "Critical",
            (RiskLevel.HIGH, RiskLevel.HIGH): "Critical",
            (RiskLevel.HIGH, RiskLevel.MEDIUM): "High",
            (RiskLevel.MEDIUM, RiskLevel.CRITICAL): "High",
            (RiskLevel.MEDIUM, RiskLevel.HIGH): "High",
            (RiskLevel.MEDIUM, RiskLevel.MEDIUM): "Medium",
            (RiskLevel.LOW, RiskLevel.CRITICAL): "Medium",
            (RiskLevel.LOW, RiskLevel.HIGH): "Medium",
            (RiskLevel.LOW, RiskLevel.MEDIUM): "Low",
        }
        return matrix.get((likelihood, impact), "Medium")

    def _identify_trust_boundaries(self, assets: list[Asset]) -> list[dict]:
        """Identify trust boundaries between assets."""
        boundaries = []

        # Group by exposure
        internet_assets = [a for a in assets if a.exposure == "internet"]
        internal_assets = [a for a in assets if a.exposure == "internal"]
        restricted_assets = [a for a in assets if a.exposure == "restricted"]

        if internet_assets and internal_assets:
            boundaries.append(
                {
                    "name": "Internet/Internal Boundary",
                    "description": "Boundary between internet-facing and internal assets",
                    "external_side": [a.asset_id for a in internet_assets],
                    "internal_side": [a.asset_id for a in internal_assets],
                    "controls": ["WAF", "Firewall", "IDS/IPS"],
                }
            )

        if internal_assets and restricted_assets:
            boundaries.append(
                {
                    "name": "Internal/Restricted Boundary",
                    "description": "Boundary protecting high-security assets",
                    "external_side": [a.asset_id for a in internal_assets],
                    "internal_side": [a.asset_id for a in restricted_assets],
                    "controls": ["Network Segmentation", "PAM", "MFA"],
                }
            )

        return boundaries

    def _map_data_flows(self, assets: list[Asset]) -> list[dict]:
        """Map data flows between assets."""
        flows = []

        # Identify databases
        databases = [a for a in assets if a.asset_type == AssetType.DATABASE]

        # Identify applications
        apps = [
            a
            for a in assets
            if a.asset_type in [AssetType.WEB_APPLICATION, AssetType.API_ENDPOINT]
        ]

        # Create flows from apps to databases
        for app in apps:
            for db in databases:
                flows.append(
                    {
                        "source": app.asset_id,
                        "destination": db.asset_id,
                        "data_type": "application_data",
                        "classification": db.data_classification,
                        "protocol": "TCP",
                        "encryption": "TLS",
                    }
                )

        return flows

    # =========================================================================
    # Attack Simulation
    # =========================================================================

    async def simulate_attack(
        self, attack_path: AttackPath, safe_mode: bool = True
    ) -> AttackSimulation:
        """
        Simulate an attack path (safe mode only performs theoretical analysis).

        Args:
            attack_path: The attack path to simulate
            safe_mode: If True, only perform theoretical analysis

        Returns:
            Simulation results
        """
        simulation_id = str(uuid.uuid4())
        started_at = datetime.now(timezone.utc)

        self._logger.info(
            "Starting attack simulation",
            simulation_id=simulation_id,
            path_id=attack_path.path_id,
            safe_mode=safe_mode,
        )

        steps_completed = 0
        steps_blocked = 0
        controls_triggered = []
        evidence = []
        findings = []
        recommendations = []

        for step in attack_path.steps:
            # Check for defensive controls that would block this step
            blocking_controls = self._check_defensive_controls(step)

            if blocking_controls:
                steps_blocked += 1
                controls_triggered.extend(blocking_controls)
                findings.append(
                    f"Step {step.step_number} ({step.name}) would be blocked by: {', '.join(blocking_controls)}"
                )
            else:
                steps_completed += 1
                findings.append(
                    f"Step {step.step_number} ({step.name}) may succeed - no blocking controls detected"
                )
                recommendations.append(
                    f"Implement controls to prevent: {step.technique_id} - {step.name}"
                )

            # Collect evidence
            evidence.append(
                {
                    "step": step.step_number,
                    "technique": step.technique_id,
                    "blocked": bool(blocking_controls),
                    "controls": blocking_controls,
                }
            )

        status = AttackStatus.BLOCKED if steps_blocked > 0 else AttackStatus.COMPLETED

        simulation = AttackSimulation(
            simulation_id=simulation_id,
            attack_path=attack_path,
            status=status,
            started_at=started_at,
            completed_at=datetime.now(timezone.utc),
            steps_completed=steps_completed,
            steps_blocked=steps_blocked,
            controls_triggered=controls_triggered,
            evidence_collected=evidence,
            findings=findings,
            recommendations=recommendations,
        )

        self._simulations[simulation_id] = simulation

        self._logger.info(
            "Attack simulation completed",
            simulation_id=simulation_id,
            status=status.value,
            steps_completed=steps_completed,
            steps_blocked=steps_blocked,
        )

        return simulation

    def _check_defensive_controls(self, step: AttackStep) -> list[str]:
        """Check what defensive controls would block an attack step."""
        _controls: list[str] = []  # noqa: F841

        technique_controls = {
            "T1190": ["WAF", "Patch Management", "Input Validation"],
            "T1078": ["MFA", "Privileged Access Management", "Account Monitoring"],
            "T1110": ["Rate Limiting", "Account Lockout", "CAPTCHA"],
            "T1552": [
                "Secrets Management",
                "Credential Rotation",
                "File Integrity Monitoring",
            ],
            "T1021": ["Network Segmentation", "Jump Servers", "Session Monitoring"],
            "T1068": ["Patch Management", "Exploit Protection", "AppLocker"],
            "T1059": [
                "PowerShell Constrained Mode",
                "Application Whitelisting",
                "Script Logging",
            ],
        }

        # Simulate random detection based on technique
        import random

        relevant_controls = technique_controls.get(step.technique_id, [])

        # Assume 40% of relevant controls are actually deployed
        deployed_controls = random.sample(
            relevant_controls,
            k=min(len(relevant_controls), max(1, int(len(relevant_controls) * 0.4))),
        )

        return deployed_controls

    # =========================================================================
    # Remediation Planning
    # =========================================================================

    async def generate_remediation_plan(
        self, attack_surface: AttackSurface
    ) -> list[RemediationPlan]:
        """
        Generate remediation plans based on attack surface analysis.

        Args:
            attack_surface: The analyzed attack surface

        Returns:
            Prioritized list of remediation plans
        """
        plans = []

        # Group vulnerabilities by severity
        critical_vulns = [
            v
            for v in attack_surface.vulnerabilities
            if v.severity == RiskLevel.CRITICAL
        ]
        high_vulns = [
            v for v in attack_surface.vulnerabilities if v.severity == RiskLevel.HIGH
        ]

        # Critical remediation plan
        if critical_vulns:
            plan = RemediationPlan(
                plan_id=str(uuid.uuid4()),
                title="Critical Vulnerability Remediation",
                findings=[v.vuln_id for v in critical_vulns],
                priority=RiskLevel.CRITICAL,
                effort_estimate="1-3 days",
                steps=[
                    RemediationStep(
                        step_number=i + 1,
                        action=f"Patch {v.title}",
                        description=v.remediation
                        or f"Apply security patch for {v.cve_id or 'vulnerability'}",
                        responsible_team="Security",
                        resources_needed=["Patch files", "Change window"],
                        verification=f"Verify {v.cve_id or 'vulnerability'} is no longer exploitable",
                    )
                    for i, v in enumerate(critical_vulns)
                ],
                expected_risk_reduction=30.0,
                verification_steps=[
                    "Run vulnerability scan",
                    "Verify patches applied",
                    "Test functionality",
                ],
            )
            plans.append(plan)

        # High priority remediation plan
        if high_vulns:
            plan = RemediationPlan(
                plan_id=str(uuid.uuid4()),
                title="High Priority Security Improvements",
                findings=[v.vuln_id for v in high_vulns],
                priority=RiskLevel.HIGH,
                effort_estimate="1-2 weeks",
                steps=[
                    RemediationStep(
                        step_number=i + 1,
                        action=f"Address {v.title}",
                        description=v.remediation or "Apply recommended remediation",
                        responsible_team="Engineering",
                        resources_needed=["Development time"],
                        verification="Verify issue resolved",
                    )
                    for i, v in enumerate(high_vulns[:10])  # Top 10
                ],
                expected_risk_reduction=20.0,
                verification_steps=["Security testing", "Code review"],
            )
            plans.append(plan)

        # Attack path mitigation plan
        if attack_surface.attack_paths:
            high_risk_paths = [
                p for p in attack_surface.attack_paths if p.success_probability > 0.5
            ]
            if high_risk_paths:
                mitigations: list[RemediationStep] = []
                for path in high_risk_paths[:5]:
                    for technique_id in path.mitre_techniques:
                        technique = self._techniques.get(technique_id)
                        if technique:
                            mitigations.append(
                                RemediationStep(
                                    step_number=len(mitigations) + 1,
                                    action=f"Mitigate {technique.name}",
                                    description=f"Implement controls for {technique_id}",
                                    responsible_team="Security",
                                    resources_needed=technique.mitigations,
                                    verification=f"Verify {technique_id} is blocked",
                                )
                            )

                plan = RemediationPlan(
                    plan_id=str(uuid.uuid4()),
                    title="Attack Path Mitigation",
                    findings=[p.path_id for p in high_risk_paths],
                    priority=RiskLevel.HIGH,
                    effort_estimate="2-4 weeks",
                    steps=mitigations[:10],
                    expected_risk_reduction=25.0,
                    verification_steps=[
                        "Re-run attack simulation",
                        "Verify controls deployed",
                    ],
                )
                plans.append(plan)

        return plans

    # =========================================================================
    # Reporting
    # =========================================================================

    def generate_executive_report(self, attack_surface: AttackSurface) -> str:
        """Generate executive summary report."""
        lines = [
            "# Attack Surface Analysis - Executive Summary",
            "",
            f"**Analysis ID:** {attack_surface.surface_id}",
            f"**Scope:** {attack_surface.name}",
            f"**Date:** {attack_surface.analyzed_at.strftime('%Y-%m-%d %H:%M UTC')}",
            "",
            "## Risk Overview",
            "",
            f"**Overall Risk Score:** {attack_surface.risk_score:.1f}/100",
            "",
            "| Category | Count |",
            "|----------|-------|",
            f"| Assets Analyzed | {len(attack_surface.assets)} |",
            f"| Vulnerabilities | {len(attack_surface.vulnerabilities)} |",
            f"| Attack Vectors | {len(attack_surface.attack_vectors)} |",
            f"| Attack Paths | {len(attack_surface.attack_paths)} |",
            "",
            "## Vulnerability Breakdown",
            "",
        ]

        # Count by severity
        severity_counts: dict[str, int] = {}
        for vuln in attack_surface.vulnerabilities:
            severity_counts[vuln.severity.value] = (
                severity_counts.get(vuln.severity.value, 0) + 1
            )

        lines.append("| Severity | Count |")
        lines.append("|----------|-------|")
        for severity in ["critical", "high", "medium", "low"]:
            count = severity_counts.get(severity, 0)
            lines.append(f"| {severity.capitalize()} | {count} |")

        lines.extend(
            [
                "",
                "## Top Attack Paths",
                "",
            ]
        )

        for i, path in enumerate(attack_surface.attack_paths[:5], 1):
            lines.append(f"{i}. **{path.name}**")
            lines.append(f"   - Success Probability: {path.success_probability:.0%}")
            lines.append(f"   - Impact: {path.total_impact.value.capitalize()}")
            lines.append(f"   - MITRE Techniques: {', '.join(path.mitre_techniques)}")
            lines.append("")

        lines.extend(
            [
                "## Recommendations",
                "",
                "1. **Immediate:** Address all critical vulnerabilities within 48 hours",
                "2. **Short-term:** Implement network segmentation to limit lateral movement",
                "3. **Medium-term:** Deploy additional monitoring for MITRE ATT&CK techniques",
                "4. **Long-term:** Conduct regular penetration testing and red team exercises",
            ]
        )

        return "\n".join(lines)

    def generate_mitre_attack_mapping(self, attack_surface: AttackSurface) -> dict:
        """Generate MITRE ATT&CK Navigator layer."""
        techniques_used = set()
        technique_scores: dict[str, float] = {}

        for path in attack_surface.attack_paths:
            for technique_id in path.mitre_techniques:
                techniques_used.add(technique_id)
                score = path.success_probability * self._risk_to_score(
                    path.total_impact
                )
                technique_scores[technique_id] = max(
                    technique_scores.get(technique_id, 0), score
                )

        # Generate Navigator layer format
        return {
            "name": f"Attack Surface Analysis - {attack_surface.name}",
            "version": "4.5",
            "domain": "enterprise-attack",
            "description": f"Attack surface analysis conducted on {attack_surface.analyzed_at}",
            "techniques": [
                {
                    "techniqueID": tid,
                    "score": min(100, int(technique_scores.get(tid, 0) * 10)),
                    "color": self._score_to_color(technique_scores.get(tid, 0)),
                }
                for tid in techniques_used
            ],
        }

    def _score_to_color(self, score: float) -> str:
        """Convert score to color for MITRE Navigator."""
        if score >= 7.5:
            return "#ff0000"  # Red
        elif score >= 5.0:
            return "#ff9900"  # Orange
        elif score >= 2.5:
            return "#ffff00"  # Yellow
        else:
            return "#00ff00"  # Green
