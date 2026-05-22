"""
Project Aura - Campaign Phase Integration Ports.

Narrow Protocols and DTOs that campaign phases call to integrate with
the rest of Aura (scanner, LLM, sandbox, HITL, deployment, evidence
packaging). Each Protocol is intentionally small — phases only see the
shape they need, never the full implementation surface.

Phases pull their dependencies from ``PhaseExecutionContext.extra``
under the ``CAMPAIGN_DEPS_KEY`` key. When a Dependencies object is not
present (or one of its ports is ``None``), phases fall back to a
deterministic stub path so the orchestrator can be exercised in
isolation. Production wires the real services in at the API layer.

Implements ADR-089 §Architecture (Components / Data Contracts).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional, Protocol

# Key under which a ``CampaignDependencies`` instance is stored in
# ``PhaseExecutionContext.extra``. Centralised so both the API layer
# (which sets it) and the phases (which read it) agree.
CAMPAIGN_DEPS_KEY: str = "campaign_deps"


# -----------------------------------------------------------------------------
# Shared DTOs
# -----------------------------------------------------------------------------


@dataclass(frozen=True)
class ScanFinding:
    """A single vulnerability finding from a baseline scan."""

    finding_id: str
    severity: str  # CRITICAL / HIGH / MEDIUM / LOW
    cwe_id: str
    file_path: str
    line_start: int
    line_end: int
    summary: str
    confidence: float  # [0, 1]


@dataclass(frozen=True)
class ScanReport:
    """Output of a baseline scan."""

    scan_id: str
    findings: tuple[ScanFinding, ...]
    standard: str  # e.g. "NIST-800-53"
    files_scanned: int
    input_tokens: int = 0
    output_tokens: int = 0


@dataclass(frozen=True)
class ComplianceGap:
    """A mapped control gap between current code and a target standard."""

    control_id: str  # e.g. "NIST-800-53 SI-10"
    description: str
    related_finding_ids: tuple[str, ...]
    severity: str
    estimated_effort_usd: float


@dataclass(frozen=True)
class GapAnalysis:
    """Mapping of findings to standard controls."""

    standard: str
    gaps: tuple[ComplianceGap, ...]
    input_tokens: int = 0
    output_tokens: int = 0


@dataclass(frozen=True)
class RemediationItem:
    """A single ranked remediation step."""

    item_id: str
    gap_control_id: str
    target_finding_ids: tuple[str, ...]
    proposed_change_summary: str
    estimated_cost_usd: float
    risk_class: str  # LOW / MEDIUM / HIGH


@dataclass(frozen=True)
class RemediationPlan:
    """A ranked plan of remediation items."""

    plan_id: str
    items: tuple[RemediationItem, ...]
    total_estimated_cost_usd: float
    input_tokens: int = 0
    output_tokens: int = 0


@dataclass(frozen=True)
class GeneratedPatch:
    """A patch produced for one remediation item."""

    patch_id: str
    remediation_item_id: str
    diff: str  # unified diff
    files_touched: tuple[str, ...]
    confidence: float
    input_tokens: int = 0
    output_tokens: int = 0


@dataclass(frozen=True)
class SandboxVerdict:
    """Verdict from running a patch in an isolated sandbox."""

    patch_id: str
    passed: bool
    tests_run: int
    tests_failed: int
    runtime_seconds: int
    sandbox_cost_usd: float = 0.0
    failure_summary: str = ""


@dataclass(frozen=True)
class HitlApprovalRequest:
    """Payload submitted to an external HITL gateway."""

    request_id: str
    campaign_id: str
    phase_id: str
    artifact_summary: str
    severity: str


@dataclass(frozen=True)
class DeploymentRecord:
    """Record of a deployment via the change-control gate."""

    deployment_id: str
    patch_ids: tuple[str, ...]
    deployed_at: datetime
    change_ticket_id: str
    rollout_strategy: str = "blue-green"


@dataclass(frozen=True)
class EvidencePackage:
    """KMS-signed compliance evidence package."""

    package_id: str  # SHA-256 of contents
    standard: str
    campaign_id: str
    tenant_id: str
    s3_key: str
    signature: str  # KMS signature
    produced_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


# -----------------------------------------------------------------------------
# Phase 1: Compliance Hardening ports
# -----------------------------------------------------------------------------


class ComplianceScannerPort(Protocol):
    async def baseline_scan(
        self, *, repo_url: str, standard: str, scan_id: str
    ) -> ScanReport:
        """Run a baseline compliance scan."""


class GapAnalyzerPort(Protocol):
    async def analyze(self, *, report: ScanReport) -> GapAnalysis:
        """Map findings to control gaps in the target standard."""


class RemediationPlannerPort(Protocol):
    async def plan(self, *, analysis: GapAnalysis) -> RemediationPlan:
        """Produce a ranked remediation plan from a gap analysis."""


class PatchGeneratorPort(Protocol):
    async def generate(self, *, item: RemediationItem, repo_url: str) -> GeneratedPatch:
        """Generate a patch for a single remediation item."""


class SandboxVerifierPort(Protocol):
    async def verify(self, *, patch: GeneratedPatch) -> SandboxVerdict:
        """Run a patch in an isolated sandbox and return the verdict."""


class HitlGatewayPort(Protocol):
    async def request_approval(self, *, request: HitlApprovalRequest) -> str:
        """Submit an approval request; return a ticket id."""


class DeploymentGatePort(Protocol):
    async def deploy(
        self,
        *,
        patches: tuple[GeneratedPatch, ...],
        change_ticket_id: str,
    ) -> DeploymentRecord:
        """Deploy approved patches via the change-control gate."""


class EvidencePackagerPort(Protocol):
    async def package(
        self,
        *,
        campaign_id: str,
        tenant_id: str,
        standard: str,
        baseline: ScanReport,
        gaps: GapAnalysis,
        plan: RemediationPlan,
        verdicts: tuple[SandboxVerdict, ...],
        deployment: DeploymentRecord,
    ) -> EvidencePackage:
        """Produce a signed compliance evidence package."""


# -----------------------------------------------------------------------------
# Phase 3: Cross-Repo Chain Analysis ports
# -----------------------------------------------------------------------------


@dataclass(frozen=True)
class RepoRef:
    """Reference to one repository in a multi-repo campaign."""

    repo_id: str
    url: str
    primary_language: str = ""


@dataclass(frozen=True)
class CrossRepoEdge:
    """A discovered cross-repo dataflow or call edge."""

    source_repo_id: str
    source_symbol: str  # e.g. "service-a:src/api/auth.py::login"
    sink_repo_id: str
    sink_symbol: str
    edge_type: str  # "dataflow" | "rpc" | "shared-library" | "queue"
    confidence: float  # [0, 1]


@dataclass(frozen=True)
class CrossRepoGraph:
    """The assembled cross-repo dependency graph."""

    repos: tuple[RepoRef, ...]
    edges: tuple[CrossRepoEdge, ...]
    input_tokens: int = 0
    output_tokens: int = 0


@dataclass(frozen=True)
class ExploitChain:
    """A discovered exploit path that crosses repositories."""

    chain_id: str
    edges: tuple[CrossRepoEdge, ...]  # ordered
    estimated_impact: str  # CRITICAL / HIGH / MEDIUM / LOW
    cwe_ids: tuple[str, ...]
    confidence: float


class RepoDiscoveryPort(Protocol):
    async def discover(self, *, fleet_target: dict) -> tuple[RepoRef, ...]:
        """Enumerate repositories in a fleet target descriptor."""


class CrossRepoGraphBuilderPort(Protocol):
    async def build(self, *, repos: tuple[RepoRef, ...]) -> CrossRepoGraph:
        """Assemble a cross-repo dataflow + call graph."""


class ExploitPathSearchPort(Protocol):
    async def search(self, *, graph: CrossRepoGraph) -> tuple[ExploitChain, ...]:
        """Search the graph for exploitable cross-repo chains."""


# -----------------------------------------------------------------------------
# Phase 4: Continuous Threat Hunting ports
# -----------------------------------------------------------------------------


@dataclass(frozen=True)
class CveFeedEntry:
    """One entry pulled from a CVE feed (NVD, GHSA, ...)."""

    cve_id: str
    published_at: datetime
    affected_components: tuple[str, ...]  # purl-like identifiers
    severity: str
    summary: str


@dataclass(frozen=True)
class RuntimeTelemetrySnapshot:
    """A point-in-time view of runtime exposure."""

    captured_at: datetime
    components_in_use: tuple[str, ...]
    suspect_processes: tuple[str, ...] = ()


@dataclass(frozen=True)
class HuntFinding:
    """A correlated CVE-vs-runtime finding worth surfacing."""

    finding_id: str
    cve_id: str
    affected_component: str
    runtime_evidence: str
    severity: str
    proposed_action: str  # "patch" | "mitigate" | "monitor"


class CveFeedPort(Protocol):
    async def poll(self, *, since: datetime) -> tuple[CveFeedEntry, ...]:
        """Return new CVE entries since the given timestamp."""


class RuntimeTelemetryPort(Protocol):
    async def snapshot(self) -> RuntimeTelemetrySnapshot:
        """Return the current runtime telemetry snapshot."""


class HuntCorrelatorPort(Protocol):
    async def correlate(
        self,
        *,
        cves: tuple[CveFeedEntry, ...],
        telemetry: RuntimeTelemetrySnapshot,
    ) -> tuple[HuntFinding, ...]:
        """Correlate CVEs against runtime telemetry."""


# -----------------------------------------------------------------------------
# Phase 6: Self-Play Security Training ports
# -----------------------------------------------------------------------------


@dataclass(frozen=True)
class TrainingCorpusRef:
    """Pointer to a curated training corpus."""

    corpus_id: str
    s3_uri: str
    sample_count: int
    domain: str  # e.g. "compliance-hardening" | "vulnerability-remediation"


@dataclass(frozen=True)
class DualRoleEpisode:
    """A single attacker-vs-defender self-play episode."""

    episode_id: str
    attacker_score: float
    defender_score: float
    transcript_s3_key: str
    duration_seconds: int


@dataclass(frozen=True)
class TrainingResult:
    """Aggregate result of a dual-role training run."""

    run_id: str
    episodes: tuple[DualRoleEpisode, ...]
    attacker_win_rate: float
    defender_win_rate: float


@dataclass(frozen=True)
class EvalResult:
    """Eval result against a held-out probe set."""

    eval_id: str
    pass_rate: float
    regressions: tuple[str, ...]
    promotion_recommended: bool


@dataclass(frozen=True)
class AdapterPromotionRecord:
    """Record of a promoted adapter (or a refusal)."""

    adapter_id: str
    promoted: bool
    reason: str


class CorpusCuratorPort(Protocol):
    async def curate(self, *, domain: str) -> TrainingCorpusRef:
        """Assemble a curated training corpus."""


class DualRolePort(Protocol):
    async def run(
        self, *, corpus: TrainingCorpusRef, episode_budget: int
    ) -> TrainingResult:
        """Run a dual-role self-play training session."""


class AdapterEvalPort(Protocol):
    async def evaluate(self, *, training: TrainingResult) -> EvalResult:
        """Evaluate trained adapter against a held-out probe set."""


class AdapterPromotionPort(Protocol):
    async def promote(self, *, eval_result: EvalResult) -> AdapterPromotionRecord:
        """Promote (or refuse to promote) an adapter."""


# -----------------------------------------------------------------------------
# Per-campaign-type Dependencies bundles
# -----------------------------------------------------------------------------


@dataclass
class ComplianceHardeningDependencies:
    """All ports a real ComplianceHardeningWorker needs.

    Each field is ``Optional`` so that partial wiring is possible —
    when a port is ``None`` the phase falls back to a stub. Tests
    inject only the ports they care about; production wires all of
    them.
    """

    scanner: Optional[ComplianceScannerPort] = None
    gap_analyzer: Optional[GapAnalyzerPort] = None
    planner: Optional[RemediationPlannerPort] = None
    patch_generator: Optional[PatchGeneratorPort] = None
    sandbox_verifier: Optional[SandboxVerifierPort] = None
    hitl_gateway: Optional[HitlGatewayPort] = None
    deployment_gate: Optional[DeploymentGatePort] = None
    evidence_packager: Optional[EvidencePackagerPort] = None
    change_ticket_id: str = ""


@dataclass
class VulnerabilityRemediationDependencies:
    """Ports for the Vulnerability Remediation worker.

    Largely overlaps with ComplianceHardeningDependencies — Phase 2 is
    "a degenerate case of the same machinery" per ADR-089 — but no
    evidence-package phase and the entry-point scanner is the
    standard vulnerability scanner rather than a compliance overlay.
    """

    scanner: Optional[ComplianceScannerPort] = None
    patch_generator: Optional[PatchGeneratorPort] = None
    sandbox_verifier: Optional[SandboxVerifierPort] = None
    hitl_gateway: Optional[HitlGatewayPort] = None
    deployment_gate: Optional[DeploymentGatePort] = None
    change_ticket_id: str = ""
    severity_floor: str = "HIGH"  # only remediate CRITICAL/HIGH by default


@dataclass
class ChainAnalysisDependencies:
    """Ports for the Cross-Repo Chain Analysis worker."""

    repo_discovery: Optional[RepoDiscoveryPort] = None
    graph_builder: Optional[CrossRepoGraphBuilderPort] = None
    path_search: Optional[ExploitPathSearchPort] = None
    hitl_gateway: Optional[HitlGatewayPort] = None
    evidence_packager: Optional[EvidencePackagerPort] = None


@dataclass
class ThreatHuntingDependencies:
    """Ports for the Continuous Threat Hunting worker.

    ``cycle_budget`` caps how many CVE-poll-correlate-act cycles a
    single "phase invocation" runs internally before returning to the
    orchestrator. Always-on campaigns are realised by the orchestrator
    re-invoking the worker on a cadence; the worker itself does not
    spin forever.
    """

    cve_feed: Optional[CveFeedPort] = None
    telemetry: Optional[RuntimeTelemetryPort] = None
    correlator: Optional[HuntCorrelatorPort] = None
    hitl_gateway: Optional[HitlGatewayPort] = None
    cycle_budget: int = 1


@dataclass
class SelfPlayTrainingDependencies:
    """Ports for the Self-Play Security Training worker."""

    corpus_curator: Optional[CorpusCuratorPort] = None
    dual_role: Optional[DualRolePort] = None
    evaluator: Optional[AdapterEvalPort] = None
    promoter: Optional[AdapterPromotionPort] = None
    episode_budget: int = 32
    domain: str = "compliance-hardening"
