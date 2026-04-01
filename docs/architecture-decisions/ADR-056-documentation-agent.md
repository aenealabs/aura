# ADR-056: Documentation Agent for Architecture Discovery and Diagram Generation

**Status:** Deployed
**Date:** 2026-01-06
**Decision Makers:** Project Aura Platform Team
**Related:** ADR-024 (Titan Neural Memory), ADR-034 (Context Engineering), ADR-037 (AWS Agent Parity), ADR-043 (Repository Onboarding), ADR-048 (Developer Tools Integration)

---

## Executive Summary

This ADR establishes a Documentation Agent for Project Aura that autonomously investigates codebases and infrastructure to generate accurate architecture diagrams, data flow diagrams, and comprehensive system documentation. This addresses a critical pain point: legacy systems and tech debt often lack adequate documentation, forcing engineers to spend days or weeks reverse-engineering systems before they can begin modernization work.

**Core Thesis:** Aura's existing GraphRAG infrastructure (Neptune + OpenSearch) already captures code relationships, dependencies, and structural information. A specialized Documentation Agent can leverage this foundation to generate high-confidence architecture visualizations and system reports, dramatically reducing the time required to understand unfamiliar systems.

**Key Outcomes:**
- Autonomous architecture diagram generation from code and IaC analysis
- Data flow diagrams showing how information moves through systems
- System discovery reports with critical insights for documentation foundations
- Infrastructure topology mapping via cloud provider API integration
- Confidence scoring with calibration to distinguish high-certainty findings from inferences
- Feedback learning to improve accuracy over time

---

## Expert Review Summary

This ADR was reviewed by six domain experts. Key findings have been incorporated:

| Expert | Focus Area | Critical Findings |
|--------|------------|-------------------|
| **Architecture Review** | Infrastructure | IAM policy syntax, GovCloud compatibility, cross-account discovery, rate limiting |
| **Security Review** | Security | Credential rotation, RBAC granularity, audit schema, data exfiltration prevention |
| **Design Review** | Frontend | Accessibility, confidence visualization, mobile responsiveness, interaction design |
| **Mike** (ML Engineer) | AI/ML | Confidence calibration, service boundary detection algorithms, feedback learning |
| **Code Review** | Code Quality | Exception hierarchy, graceful degradation, streaming/pagination, testability |
| **Tyler** (Data Engineer) | Data Infrastructure | Neptune schema extensions, caching strategy, incremental updates |

---

## Context

### The Problem: Documentation Debt in Enterprise Systems

Engineering teams routinely encounter systems with inadequate documentation:

| Scenario | Impact |
|----------|--------|
| Legacy system modernization | 2-4 weeks spent reverse-engineering before work begins |
| Post-acquisition integration | No tribal knowledge, scattered/outdated docs |
| Incident response on unfamiliar system | Extended MTTR due to discovery time |
| Compliance audits | Manual effort to create required architecture diagrams |
| New team member onboarding | Months to build mental model of complex systems |

**Industry Data:**
- Stripe (2023): Developers spend ~42% of time on maintenance/tech debt, largely due to poor documentation
- McKinsey: Technical debt costs enterprises $5.3 trillion annually; documentation debt is a major contributor
- Stack Overflow Survey: 65% of developers say lack of documentation is a top productivity blocker

### What Aura Already Captures

Project Aura's GraphRAG infrastructure already builds comprehensive code understanding:

#### Neptune Graph Entities (from `src/services/neptune_graph_service.py`)

| Entity Type | Relationships | Documentation Value |
|-------------|---------------|---------------------|
| `CodeFile` | IMPORTS, CONTAINS, REFERENCES | File dependency maps |
| `Function` | CALLS, CALLED_BY, IMPLEMENTS | Call graphs |
| `Class` | EXTENDS, IMPLEMENTS, USES | Inheritance diagrams |
| `Package` | DEPENDS_ON, EXPORTS | Module structure |
| `API` | SERVES, CONSUMES | Service boundaries |
| `Database` | READS, WRITES, OWNS | Data flow |
| `Queue` | PUBLISHES, SUBSCRIBES | Event architecture |
| `Config` | CONFIGURES, REFERENCES | Configuration topology |

#### Existing Query Capabilities (from `src/services/context_retrieval_service.py`)

```python
# Already implemented search types
class GraphSearchType(Enum):
    CALL_GRAPH = "call_graph"           # Function call relationships
    DEPENDENCIES = "dependencies"        # Package/module dependencies
    INHERITANCE = "inheritance"          # Class hierarchies
    REFERENCES = "references"            # Cross-file references
    RELATED = "related"                  # Semantically similar code
```

#### IaC Already Parsed

The repository onboarding wizard (ADR-043) already parses:
- CloudFormation templates -> Resource relationships
- Terraform configurations -> Infrastructure dependencies
- Kubernetes manifests -> Service topology
- Docker Compose files -> Container relationships

### The Gap: No Documentation Synthesis

Despite rich underlying data, Aura cannot currently:

| Capability | Data Available | Synthesis Available |
|------------|----------------|---------------------|
| Generate architecture diagrams | Yes (Graph relationships) | No diagram generation |
| Create data flow diagrams | Yes (Database/queue edges) | No visualization |
| Produce system reports | Yes (All entity metadata) | No report templates |
| Discover cloud infrastructure | No (Not integrated) | N/A |
| Correlate code with runtime | No (Not integrated) | N/A |

---

## Decision

**Implement a Documentation Agent that leverages existing GraphRAG infrastructure to generate architecture diagrams, data flow visualizations, and system documentation with confidence-scored findings and feedback-driven calibration.**

### Architecture Overview

```
                    DOCUMENTATION AGENT ARCHITECTURE

    LAYER 1: DATA SOURCES
    +------------------+  +------------------+  +------------------+  +------------------+
    |     Neptune      |  |    OpenSearch    |  |    IaC Parser    |  | Cloud Provider   |
    |    GraphRAG      |  |     Vectors      |  |    (exists)      |  |  APIs (Phase 2)  |
    |    (exists)      |  |    (exists)      |  |                  |  |                  |
    +--------+---------+  +--------+---------+  +--------+---------+  +--------+---------+
             |                     |                     |                     |
             +---------------------+---------------------+---------------------+
                                   |
    LAYER 2: ANALYSIS ENGINE       |
    +------------------------------v----------------------------------------------+
    |                         DOCUMENTATION AGENT                                  |
    |  +-------------------+  +-------------------+  +-------------------------+  |
    |  | Service Boundary  |  | Data Flow         |  | Infrastructure          |  |
    |  | Detector          |  | Analyzer          |  | Mapper                  |  |
    |  | (Louvain algo)    |  |                   |  |                         |  |
    |  +-------------------+  +-------------------+  +-------------------------+  |
    |  +-------------------+  +-------------------+  +-------------------------+  |
    |  | Dependency        |  | API Contract      |  | Confidence              |  |
    |  | Resolver          |  | Extractor         |  | Scorer + Calibrator     |  |
    |  +-------------------+  +-------------------+  +-------------------------+  |
    +----------------------------------+----------------------------------------------+
                                       |
    LAYER 3: OUTPUT GENERATION         |
    +----------------------------------v----------------------------------------------+
    |  +-------------------+  +-------------------+  +-------------------------+     |
    |  | Diagram           |  | Report            |  | Export                  |     |
    |  | Generator         |  | Generator         |  | Formatter               |     |
    |  | (Mermaid/D2)      |  | (Markdown)        |  | (PDF/PNG/SVG)           |     |
    |  +-------------------+  +-------------------+  +-------------------------+     |
    +---------------------------------------------------------------------------------+

    LAYER 4: CACHING & PERSISTENCE
    +---------------------------------------------------------------------------------+
    |  L1: In-Memory (5min)  |  L2: Redis (1hr)  |  L3: S3 (24hr)  |  DynamoDB Meta  |
    +---------------------------------------------------------------------------------+
```

### Component Details

#### 1. Exception Hierarchy (Code Review)

```python
# src/agents/documentation_agent_exceptions.py

class DocumentationAgentError(Exception):
    """Base exception for Documentation Agent operations."""

class GraphTraversalError(DocumentationAgentError):
    """Raised when graph traversal fails or returns partial results."""
    def __init__(self, message: str, partial_results: list | None = None):
        super().__init__(message)
        self.partial_results = partial_results or []

class DiagramGenerationError(DocumentationAgentError):
    """Raised when diagram rendering fails."""

class InsufficientDataError(DocumentationAgentError):
    """Raised when confidence threshold cannot be met."""
    def __init__(self, message: str, confidence: float, threshold: float):
        super().__init__(message)
        self.confidence = confidence
        self.threshold = threshold

class CloudDiscoveryError(DocumentationAgentError):
    """Raised when cloud provider API calls fail."""

class CredentialError(DocumentationAgentError):
    """Raised for credential access or validation failures."""
```

#### 2. Type Definitions

```python
# src/agents/documentation_agent_types.py

from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
import re

class DiagramType(Enum):
    COMPONENT = "component"
    DEPLOYMENT = "deployment"
    DATA_FLOW = "data_flow"
    SEQUENCE = "sequence"
    CLASS = "class"
    DEPENDENCY = "dependency"

class DiagramScope(Enum):
    FULL = "full"
    SERVICE = "service"
    MODULE = "module"
    PATH = "path"

class DiagramFormat(Enum):
    MERMAID = "mermaid"
    D2 = "d2"
    PLANTUML = "plantuml"
    DOT = "dot"

class ReportType(Enum):
    OVERVIEW = "overview"
    SECURITY = "security"
    DEPENDENCIES = "dependencies"
    DATA_FLOW = "data_flow"

class ElementType(Enum):
    SERVICE = "service"
    DATABASE = "database"
    QUEUE = "queue"
    API = "api"
    FUNCTION = "function"
    CLASS = "class"
    EXTERNAL = "external"
    CACHE = "cache"
    STORAGE = "storage"

class ConfidenceLevel(Enum):
    VERIFIED = "verified"        # 0.95+ - Multiple strong evidence sources
    HIGH = "high"                # 0.80-0.94 - Clear code evidence
    MEDIUM = "medium"            # 0.60-0.79 - Inferred with some uncertainty
    LOW = "low"                  # 0.40-0.59 - Weak evidence, needs validation
    UNCERTAIN = "uncertain"      # <0.40 - Speculation, flagged for review

class DataClassification(Enum):
    """Data sensitivity classification for PII tracking."""
    PII = "pii"
    PHI = "phi"
    FINANCIAL = "financial"
    CREDENTIALS = "credentials"
    INTERNAL = "internal"
    PUBLIC = "public"

VALID_REPO_ID_PATTERN = re.compile(r'^[a-zA-Z0-9_-]+/[a-zA-Z0-9_.-]+$')

def validate_repository_id(repo_id: str) -> str:
    """Validate repository ID format to prevent injection."""
    if not repo_id or not VALID_REPO_ID_PATTERN.match(repo_id):
        raise ValueError(
            f"Invalid repository_id format: {repo_id}. "
            "Expected format: 'owner/repo-name'"
        )
    return repo_id
```

#### 3. Documentation Agent Core (`src/agents/documentation_agent.py`)

```python
from typing import AsyncIterator, Optional
from dataclasses import dataclass, field

from src.agents.base_agent import BaseAgent, MCPToolMixin
from src.services.neptune_graph_service import NeptuneGraphService
from src.services.opensearch_vector_service import OpenSearchVectorService
from src.services.bedrock_llm_service import BedrockLLMService

@dataclass
class DiagramElement:
    """Element in a generated diagram with confidence metadata."""
    id: str
    element_type: ElementType
    label: str
    confidence: float
    confidence_factors: list
    source_evidence: list

    def __post_init__(self):
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(f"Confidence must be in [0.0, 1.0], got {self.confidence}")
        if not self.id:
            raise ValueError("Element ID cannot be empty")
        if not self.label:
            raise ValueError("Element label cannot be empty")

@dataclass
class DiagramChunk:
    """Streaming chunk for large diagram generation."""
    elements: list[DiagramElement]
    page_token: str | None
    total_elements: int
    progress_percent: float

@dataclass
class DiagramGenerationResult:
    """Result wrapper with success/partial success distinction."""
    diagram: Optional["ArchitectureDiagram"]
    status: str  # "success", "partial", "failed"
    elements_retrieved: int
    elements_expected: int | None
    warnings: list[str]
    errors: list[str]

class DocumentationAgent(MCPToolMixin, BaseAgent):
    """
    Autonomous agent for architecture discovery and documentation generation.

    Leverages GraphRAG (Neptune + OpenSearch) to extract system structure
    and generate high-confidence architecture visualizations.
    """

    def __init__(
        self,
        neptune_client: NeptuneGraphService,
        opensearch_client: OpenSearchVectorService,
        iac_parser: "IaCParserService",
        llm_client: BedrockLLMService | None = None,
        cloud_discovery_client: "CloudDiscoveryService | None" = None,
        confidence_threshold: float = 0.7,
    ):
        super().__init__(llm_client=llm_client, agent_name="DocumentationAgent")

        self.neptune = neptune_client
        self.opensearch = opensearch_client
        self.iac_parser = iac_parser
        self.cloud_discovery = cloud_discovery_client
        self.confidence_threshold = confidence_threshold

        # Calibration (Phase 1.5)
        self._calibrator = CalibratedConfidenceScorer()

        # Service boundary detector (Louvain algorithm)
        self._boundary_detector = ServiceBoundaryDetector(neptune_client)

        # Diagram cache
        self._diagram_cache: dict[str, tuple] = {}
        self.DIAGRAM_CACHE_TTL_SECONDS = 3600

    async def generate_architecture_diagram(
        self,
        repository_id: str,
        diagram_type: DiagramType,
        scope: DiagramScope = DiagramScope.FULL,
        format: DiagramFormat = DiagramFormat.MERMAID,
        max_elements: int = 500,
    ) -> DiagramGenerationResult:
        """
        Generate architecture diagram from code and infrastructure analysis.

        Args:
            repository_id: Target repository (validated format: owner/repo)
            diagram_type: COMPONENT, DEPLOYMENT, DATA_FLOW, SEQUENCE, CLASS
            scope: FULL, SERVICE, MODULE, or specific path
            format: MERMAID, D2, PLANTUML, DOT
            max_elements: Maximum elements to include (for large codebases)

        Returns:
            DiagramGenerationResult with diagram, status, and metadata
        """
        validate_repository_id(repository_id)

        warnings = []
        errors = []

        try:
            # Check cache first
            cache_key = f"{repository_id}:{diagram_type.value}:{scope.value}"
            cached = self._get_cached_diagram(cache_key)
            if cached:
                return DiagramGenerationResult(
                    diagram=cached,
                    status="success",
                    elements_retrieved=len(cached.elements),
                    elements_expected=None,
                    warnings=["Served from cache"],
                    errors=[]
                )

            # Detect service boundaries using Louvain algorithm
            boundaries = await self._boundary_detector.detect_boundaries(
                repository_id=repository_id,
                max_services=20,
            )

            # Generate diagram elements
            elements = await self._generate_elements(
                repository_id, diagram_type, scope, boundaries, max_elements
            )

            # Check confidence threshold
            avg_confidence = sum(e.confidence for e in elements) / len(elements) if elements else 0
            if avg_confidence < self.confidence_threshold:
                raise InsufficientDataError(
                    f"Average confidence {avg_confidence:.2f} below threshold {self.confidence_threshold}",
                    confidence=avg_confidence,
                    threshold=self.confidence_threshold
                )

            # Render diagram
            diagram = await self._render_diagram(elements, format, diagram_type)

            # Cache result
            self._cache_diagram(cache_key, diagram)

            return DiagramGenerationResult(
                diagram=diagram,
                status="success",
                elements_retrieved=len(elements),
                elements_expected=len(elements),
                warnings=warnings,
                errors=errors
            )

        except GraphTraversalError as e:
            # Return partial results on traversal failure
            return DiagramGenerationResult(
                diagram=None,
                status="partial",
                elements_retrieved=len(e.partial_results),
                elements_expected=None,
                warnings=["Graph traversal incomplete"],
                errors=[str(e)]
            )
        except InsufficientDataError:
            raise
        except Exception as e:
            logger.error(f"Diagram generation failed: {e}", exc_info=True)
            raise DiagramGenerationError(str(e)) from e

    async def generate_architecture_diagram_streaming(
        self,
        repository_id: str,
        diagram_type: DiagramType,
        scope: DiagramScope = DiagramScope.FULL,
        format: DiagramFormat = DiagramFormat.MERMAID,
        max_elements: int = 500,
        page_token: str | None = None,
    ) -> AsyncIterator[DiagramChunk]:
        """
        Stream diagram generation for large codebases.

        Yields DiagramChunk objects with incremental progress.
        """
        validate_repository_id(repository_id)
        # Implementation uses pagination through Neptune results
        ...

    async def generate_system_report(
        self,
        repository_id: str,
        report_type: ReportType,
        include_recommendations: bool = True,
    ) -> "SystemReport":
        """
        Generate comprehensive system documentation report.
        """
        validate_repository_id(repository_id)
        ...
```

#### 4. Service Boundary Detector (Mike's Review - Louvain Algorithm)

```python
# src/agents/service_boundary_detector.py

import networkx as nx
from dataclasses import dataclass

@dataclass
class ServiceBoundary:
    """Detected service boundary."""
    service_id: str
    name: str
    files: list[str]
    entry_points: list[str]
    dependencies: list[str]
    confidence: float

class ServiceBoundaryDetector:
    """
    Detects service boundaries using community detection on the code graph.

    Algorithm: Louvain modularity optimization
    Input: Neptune graph of code entities and relationships
    Output: Partition of code into logical services
    """

    def __init__(self, graph_service: NeptuneGraphService):
        self.graph = graph_service
        self.resolution = 1.0  # Louvain resolution parameter

    async def detect_boundaries(
        self,
        repository_id: str,
        min_service_size: int = 5,
        max_services: int = 20,
    ) -> list[ServiceBoundary]:
        """
        Detect service boundaries using multi-signal approach.

        Signals combined:
        1. Code structure (call graph communities) - weight 0.80
        2. File system organization (directory structure) - weight 0.70
        3. Import patterns (module dependencies) - weight 0.75
        4. Deployment units (IaC definitions) - weight 0.95 (ground truth when available)
        """
        # 1. Build weighted graph from Neptune
        G = await self._build_weighted_graph(repository_id)

        if len(G.nodes) == 0:
            return []

        # 2. Apply Louvain community detection
        communities = nx.community.louvain_communities(
            G,
            resolution=self.resolution,
            seed=42  # Reproducibility
        )

        # 3. Refine with directory structure
        refined = self._refine_with_directories(communities, G)

        # 4. Validate with IaC definitions (ground truth when available)
        validated = await self._validate_with_iac(refined, repository_id)

        return self._build_service_boundaries(validated, min_service_size, max_services)

    async def _build_weighted_graph(self, repo_id: str) -> nx.Graph:
        """
        Build NetworkX graph from Neptune with edge weights.

        Edge weights based on relationship strength:
        - CALLS: 1.0 (strong coupling)
        - IMPORTS: 0.8 (dependency)
        - EXTENDS: 0.9 (inheritance)
        - REFERENCES: 0.5 (loose coupling)
        """
        entities = await self.graph.search_by_name("*", limit=10000)

        G = nx.Graph()

        relationship_weights = {
            "CALLS": 1.0,
            "IMPORTS": 0.8,
            "EXTENDS": 0.9,
            "REFERENCES": 0.5,
        }

        for entity in entities:
            G.add_node(
                entity["id"],
                file_path=entity.get("file_path"),
                entity_type=entity.get("type"),
            )

        # Add weighted edges
        for entity in entities:
            related = await self.graph.find_related_code(
                entity_name=entity["name"],
                max_depth=1
            )
            for rel in related:
                weight = relationship_weights.get(rel.get("relationship"), 0.5)
                G.add_edge(entity["id"], rel["id"], weight=weight)

        return G
```

#### 5. Confidence Calibration System (Mike's Review)

```python
# src/agents/confidence_calibrator.py

from sklearn.isotonic import IsotonicRegression
from dataclasses import dataclass, field
from datetime import datetime, timezone

@dataclass
class ConfidenceFactor:
    """Factor contributing to confidence score."""
    factor: str
    weight: float
    evidence: str

# Base weights for evidence types
EVIDENCE_WEIGHTS = {
    "explicit_iac_definition": 0.95,
    "api_contract_openapi": 0.90,
    "code_import_statement": 0.85,
    "database_connection_string": 0.85,
    "function_call_pattern": 0.75,
    "configuration_reference": 0.70,
    "naming_convention_match": 0.50,
    "semantic_similarity": 0.40,
    "llm_generated": 0.70,  # LLM descriptions start at medium confidence
}

class CalibratedConfidenceScorer:
    """
    Calibrates raw confidence scores using isotonic regression.
    Maps predicted confidence -> empirical accuracy after collecting validations.
    """

    def __init__(self, min_samples_for_calibration: int = 100):
        self.calibrator = IsotonicRegression(out_of_bounds='clip')
        self.raw_scores: list[float] = []
        self.actual_outcomes: list[int] = []
        self.is_calibrated = False
        self.min_samples = min_samples_for_calibration

    def calculate_raw_confidence(self, factors: list[ConfidenceFactor]) -> float:
        """Calculate raw confidence from evidence factors."""
        if not factors:
            return 0.0

        # Weighted combination using Dempster-Shafer inspired approach
        combined = 0.0
        total_weight = 0.0

        for factor in factors:
            base_weight = EVIDENCE_WEIGHTS.get(factor.factor, 0.5)
            combined += base_weight * factor.weight
            total_weight += factor.weight

        return combined / total_weight if total_weight > 0 else 0.0

    def record_feedback(self, raw_score: float, was_correct: bool) -> None:
        """Record user validation for calibration training."""
        self.raw_scores.append(raw_score)
        self.actual_outcomes.append(1 if was_correct else 0)

        if len(self.raw_scores) >= self.min_samples and not self.is_calibrated:
            self._fit_calibrator()

    def _fit_calibrator(self) -> None:
        """Fit isotonic regression on collected data."""
        import numpy as np
        self.calibrator.fit(
            np.array(self.raw_scores).reshape(-1, 1),
            np.array(self.actual_outcomes)
        )
        self.is_calibrated = True

    def calibrate(self, raw_score: float) -> float:
        """Return calibrated probability."""
        if not self.is_calibrated:
            return raw_score
        import numpy as np
        return float(self.calibrator.predict([[raw_score]])[0])

def compute_expected_calibration_error(
    predicted: list[float],
    actual: list[bool],
    n_bins: int = 10
) -> float:
    """
    Expected Calibration Error - measures calibration quality.
    Target: ECE < 0.05 (within 5% of predicted confidence)
    """
    import numpy as np
    predicted = np.array(predicted)
    actual = np.array(actual)

    bin_boundaries = np.linspace(0, 1, n_bins + 1)
    ece = 0.0

    for i in range(n_bins):
        in_bin = (predicted >= bin_boundaries[i]) & (predicted < bin_boundaries[i + 1])

        if np.sum(in_bin) > 0:
            accuracy = np.mean(actual[in_bin])
            avg_confidence = np.mean(predicted[in_bin])
            ece += np.abs(accuracy - avg_confidence) * np.sum(in_bin)

    return ece / len(predicted) if len(predicted) > 0 else 0.0
```

#### 6. Feedback Learning System (Mike's Review)

```python
# src/agents/feedback_learning_service.py

@dataclass
class DocumentationFeedback:
    """User feedback on generated documentation."""
    element_id: str
    feedback_type: str  # "correct", "incorrect", "partially_correct", "missing"
    user_correction: str | None = None
    original_confidence: float = 0.0
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    user_id: str = ""

class FeedbackLearningService:
    """
    Learn from user feedback to improve future generations.

    Learning signals:
    1. Confidence calibration (isotonic regression)
    2. Evidence weight adjustment (exponential moving average)
    3. Correction storage for few-shot prompting
    """

    def __init__(self, dynamodb_client):
        self.db = dynamodb_client
        self.calibrator = CalibratedConfidenceScorer()
        self.evidence_weights = dict(EVIDENCE_WEIGHTS)
        self._alpha = 0.1  # Learning rate for weight updates

    async def record_feedback(self, feedback: DocumentationFeedback) -> None:
        """Record feedback and update models."""
        # Store feedback
        await self.db.put_item(
            TableName="aura-documentation-feedback",
            Item=feedback.__dict__
        )

        # Update calibrator
        was_correct = feedback.feedback_type == "correct"
        self.calibrator.record_feedback(feedback.original_confidence, was_correct)

        # Store correction for few-shot prompting
        if feedback.user_correction:
            await self._store_correction(feedback)

    async def get_few_shot_examples(
        self,
        element_type: str,
        k: int = 3,
    ) -> list[dict]:
        """Get recent corrections as few-shot examples for LLM prompting."""
        response = await self.db.query(
            TableName="aura-documentation-corrections",
            KeyConditionExpression="element_type = :et",
            ExpressionAttributeValues={":et": element_type},
            Limit=k,
            ScanIndexForward=False,
        )
        return response.get("Items", [])
```

### Neptune Schema Extensions (Tyler's Review)

The existing Neptune schema needs enrichment for documentation generation:

#### New Vertex Labels

```python
# InfrastructureResource vertex
{
    "resource_id": "string (primary key)",
    "resource_type": "string (RDS, DynamoDB, SQS, S3, Lambda, etc.)",
    "logical_name": "string (from IaC)",
    "physical_name": "string (from cloud discovery - Phase 2)",
    "provider": "string (aws, azure, gcp)",
    "region": "string",
    "iac_source_file": "string",
    "iac_source_line": "int",
    "properties": "map (JSON blob for resource-specific config)",
    "repository_id": "string",
    "created_at": "timestamp",
    "last_discovered_at": "timestamp",
    "confidence_score": "float"
}

# ServiceBoundary vertex
{
    "service_id": "string",
    "name": "string",
    "description": "string",
    "entry_points": "list[string] (API endpoints)",
    "team_owner": "string",
    "repo_root_path": "string",
    "repository_id": "string",
    "detected_at": "timestamp",
    "confidence_score": "float"
}

# DataFlow vertex
{
    "flow_id": "string",
    "source_type": "string (API, Queue, Database, File)",
    "source_id": "string",
    "target_type": "string",
    "target_id": "string",
    "data_classification": "string (PII, SENSITIVE, PUBLIC)",
    "volume_estimate": "string (HIGH, MEDIUM, LOW)",
    "repository_id": "string",
    "confidence_score": "float"
}
```

#### New Edge Types

| Edge Type | Source | Target | Properties |
|-----------|--------|--------|------------|
| `CONNECTS_TO` | InfrastructureResource | InfrastructureResource | protocol, port, tls |
| `OWNED_BY` | InfrastructureResource | ServiceBoundary | confidence_score |
| `PRODUCES_TO` | ServiceBoundary | Queue/Topic | event_type, schema_ref |
| `CONSUMES_FROM` | ServiceBoundary | Queue/Topic | event_type, schema_ref |
| `READS_FROM` | ServiceBoundary | Database | access_pattern, tables |
| `WRITES_TO` | ServiceBoundary | Database | access_pattern, tables |
| `CALLS` | ServiceBoundary | ServiceBoundary | protocol, endpoint |

### Caching Strategy (Tyler's Review)

Three-tier caching for diagram generation:

| Tier | Storage | TTL | Purpose |
|------|---------|-----|---------|
| L1 | In-memory | 5 min | Active diagram editing session |
| L2 | ElastiCache/Redis | 1 hour | Recently generated diagrams |
| L3 | S3 | 24 hours | Completed diagram artifacts |

**Cache Key Structure:**
```
diagram:{repository_id}:{diagram_type}:{scope_hash}:{graph_version}
```

**Invalidation Patterns:**
1. On code push: Publish `aura.repository.updated` to EventBridge
2. On threshold change: Include threshold in cache key
3. TTL expiration: Mark stale, regenerate on demand

### Incremental Update Strategy (Tyler's Review)

For large codebases, full regeneration on every change is expensive:

```
Code Push
    |
    v
Repository Ingestion (existing)
    |
    v
Delta Detection
  - Compare new graph state vs. previous
  - Identify added, modified, deleted vertices/edges
    |
    v
Affected Diagram Query
  - Query diagram-dependencies table
  - Get list of diagrams needing refresh
    |
    v
Prioritized Regeneration Queue
  - High: >20% vertices changed -> immediate regeneration
  - Medium: 5-20% changed -> background regeneration
  - Low: <5% changed -> mark stale, regenerate on demand
```

### Diagram Types

| Diagram Type | Data Sources | Output |
|--------------|--------------|--------|
| **Component Diagram** | Service boundaries, API contracts, dependencies | High-level service architecture |
| **Deployment Diagram** | IaC files, cloud resources, container definitions | Infrastructure topology |
| **Data Flow Diagram** | Database edges, queue subscriptions, API calls | Information movement |
| **Sequence Diagram** | Call graphs, event chains | Request/response flows |
| **Class Diagram** | Inheritance, interfaces, associations | Object model |
| **Dependency Graph** | Package imports, external dependencies | Dependency topology |

### Cloud Discovery Integration (Phase 2)

#### Cross-Account Discovery Architecture (Architecture Review)

```python
class CrossAccountDiscovery:
    """
    Cross-account discovery using IAM role assumption.
    Requires: Discovery role in each member account.
    """

    GOVCLOUD_REGIONS = {"us-gov-west-1", "us-gov-east-1"}

    async def discover_account(
        self, account_id: str, discovery_role: str = "AuraDiscoveryRole"
    ) -> list:
        # Get partition (aws vs aws-us-gov)
        partition = self._get_partition()

        # Assume role in target account
        role_arn = f"arn:{partition}:iam::{account_id}:role/{discovery_role}"
        assumed_session = await self._assume_role(
            role_arn=role_arn,
            session_name="AuraDocAgent",
            external_id=self._get_external_id(account_id)
        )

        return await self._discover_with_session(assumed_session)

    def _get_partition(self) -> str:
        """Return aws or aws-us-gov based on current region."""
        region = os.environ.get("AWS_REGION", "us-east-1")
        if region in self.GOVCLOUD_REGIONS:
            return "aws-us-gov"
        return "aws"
```

#### GovCloud Compatibility (Architecture Review)

Services NOT available in GovCloud (require fallbacks):
- AWS Application Discovery Service -> Use AWS Config instead
- AWS Resource Explorer -> Use direct service Describe calls
- AWS Service Catalog AppRegistry -> Limited functionality

```python
class AWSDiscoveryProvider:
    GOVCLOUD_UNAVAILABLE_SERVICES = {
        "discovery",
        "resource-explorer-2",
    }

    def __init__(self, session):
        self.is_govcloud = session.region_name.startswith("us-gov")
        if self.is_govcloud:
            self._configure_govcloud_fallbacks()

    def _configure_govcloud_fallbacks(self):
        """Use AWS Config as primary discovery in GovCloud."""
        self.use_config_for_discovery = True
```

#### Circuit Breaker Pattern (Code Review)

```python
from dataclasses import dataclass
from datetime import timedelta

@dataclass
class CircuitBreakerState:
    failures: int = 0
    last_failure: datetime | None = None
    state: str = "closed"  # closed, open, half-open

class CloudDiscoveryService:
    def __init__(self, ...):
        self._circuit_breakers: dict[str, CircuitBreakerState] = {}
        self._failure_threshold = 5
        self._recovery_timeout = timedelta(minutes=5)

    def _is_circuit_open(self, provider_name: str) -> bool:
        state = self._circuit_breakers.get(provider_name)
        if not state or state.state == "closed":
            return False
        if state.state == "open":
            if datetime.now() - state.last_failure > self._recovery_timeout:
                state.state = "half-open"
                return False
            return True
        return False
```

#### IAM Policy Design (Architecture Review - Fixed Syntax)

```yaml
# Correct IAM policy format - explicit service:action (not wildcards)
Statement:
  - Sid: AllowReadOnlyDiscovery
    Effect: Allow
    Action:
      # EC2
      - ec2:DescribeInstances
      - ec2:DescribeVpcs
      - ec2:DescribeSubnets
      - ec2:DescribeSecurityGroups
      # ECS
      - ecs:DescribeClusters
      - ecs:DescribeServices
      - ecs:ListTasks
      # EKS
      - eks:DescribeCluster
      - eks:ListNodegroups
      # RDS
      - rds:DescribeDBInstances
      - rds:DescribeDBClusters
      # DynamoDB
      - dynamodb:DescribeTable
      - dynamodb:ListTables
      # S3 (restricted - no GetBucketPolicy to prevent IAM exposure)
      - s3:ListBuckets
      - s3:GetBucketLocation
      - s3:GetBucketTagging
      # Lambda (no GetFunction to prevent code download)
      - lambda:ListFunctions
      - lambda:GetFunctionConfiguration
      # Config (for relationship discovery)
      - config:SelectResourceConfig
      - config:GetResourceConfigHistory
      # Resource Groups Tagging
      - tag:GetResources
    Resource: "*"

  - Sid: ExplicitDenyMutations
    Effect: Deny
    Action:
      - ec2:Create*
      - ec2:Delete*
      - ec2:Modify*
      - ec2:Terminate*
      - ecs:Create*
      - ecs:Delete*
      - ecs:Update*
      - rds:Create*
      - rds:Delete*
      - rds:Modify*
      - s3:Put*
      - s3:Delete*
      - lambda:Create*
      - lambda:Delete*
      - lambda:Update*
    Resource: "*"
```

### Security Model (Security Review - Enhanced)

#### Granular RBAC Permissions

```python
DOCUMENTATION_PERMISSIONS = {
    # Diagram generation - granular by type
    "docs:generate:component": "Generate component diagrams",
    "docs:generate:deployment": "Generate deployment diagrams (requires cloud:discover:*)",
    "docs:generate:dataflow": "Generate data flow diagrams",
    "docs:generate:sequence": "Generate sequence diagrams",
    "docs:generate:class": "Generate class diagrams",

    # View permissions
    "docs:view": "View generated documentation",
    "docs:view:sensitive": "View diagrams with full network details",

    # Export permissions
    "docs:export:basic": "Export diagrams with redacted sensitive data",
    "docs:export:sensitive": "Export diagrams with full network/security details",
    "docs:export:bulk": "Export multiple diagrams at once",

    # Cloud discovery - per provider
    "cloud:discover:aws": "Discover AWS resources",
    "cloud:discover:azure": "Discover Azure resources",
    "cloud:discover:gcp": "Discover GCP resources",

    # Credential management - separation of duties
    "cloud:credentials:view": "View configured cloud connections (not credentials)",
    "cloud:credentials:configure": "Add/modify cloud credentials",
    "cloud:credentials:approve": "Approve new cloud account connections",
    "cloud:credentials:rotate": "Trigger credential rotation",
    "cloud:credentials:delete": "Remove cloud credentials",
}
```

#### Credential Management

```python
class CloudCredentialService:
    """
    Secure credential management for cloud discovery.

    - Credentials stored in Secrets Manager (not Aura DB)
    - 90-day automatic rotation via Lambda
    - Credential proxy prevents agent code from seeing raw credentials
    """

    ROTATION_DAYS = 90

    async def get_discovery_session(
        self, provider: str, account_id: str
    ) -> "AuthenticatedSession":
        """
        Return pre-authenticated session.
        Agent code never sees raw credentials.
        """
        secret_name = f"aura/{self.org_id}/cloud-discovery/{provider}/{account_id}"

        # Validate credential exists and is not expired
        secret = await self.secrets_manager.get_secret_value(SecretId=secret_name)

        # Create authenticated session
        if provider == "aws":
            return self._create_aws_session(secret)
        elif provider == "azure":
            return self._create_azure_session(secret)
        # ...

    async def rotate_credentials(self, provider: str, account_id: str) -> None:
        """Trigger credential rotation."""
        # Invoke rotation Lambda
        ...
```

#### Data Exfiltration Prevention

```python
class DiagramExportClassification(Enum):
    PUBLIC = "public"           # Can be shared externally
    INTERNAL = "internal"       # Within organization only
    CONFIDENTIAL = "confidential"  # Need-to-know only
    RESTRICTED = "restricted"   # Requires explicit approval

ELEMENT_CLASSIFICATION = {
    "security_group_rules": DiagramExportClassification.RESTRICTED,
    "vpc_cidr_blocks": DiagramExportClassification.CONFIDENTIAL,
    "database_endpoints": DiagramExportClassification.CONFIDENTIAL,
    "api_gateway_urls": DiagramExportClassification.INTERNAL,
    "service_names": DiagramExportClassification.INTERNAL,
}

class DiagramRedactionService:
    """
    Redact sensitive information from diagrams by default.
    Full details require docs:export:sensitive permission.
    """

    def redact_for_export(
        self, diagram: ArchitectureDiagram, user_permissions: list[str]
    ) -> ArchitectureDiagram:
        if "docs:export:sensitive" not in user_permissions:
            return self._apply_redactions(diagram)
        return diagram

    def _apply_redactions(self, diagram: ArchitectureDiagram) -> ArchitectureDiagram:
        """Apply default redactions."""
        for element in diagram.elements:
            if element.element_type == "security_group":
                element.properties["rules"] = "[REDACTED]"
            if "ip_address" in element.properties:
                element.properties["ip_address"] = "10.x.x.x"
            if "cidr" in element.properties:
                element.properties["cidr"] = "[PRIVATE SUBNET]"
        return diagram
```

#### Enhanced Audit Logging (Security Review)

```python
@dataclass
class DocumentationAuditEvent:
    """Enhanced audit event for NIST 800-53 AU-3 compliance."""

    # Identity and context
    event_id: str
    event_type: str
    user_id: str
    organization_id: str
    repository_id: str
    session_id: str
    request_id: str
    source_ip_address: str
    user_agent: str

    # Operation details
    diagram_type: str | None = None
    report_type: str | None = None

    # Cloud discovery specifics
    cloud_providers_accessed: list[str] | None = None
    cloud_accounts_accessed: list[str] | None = None
    cloud_regions_accessed: list[str] | None = None
    resources_discovered_count: int = 0

    # Output metrics
    elements_generated: int = 0
    confidence_average: float = 0.0
    sensitive_elements_included: bool = False
    sensitive_element_types: list[str] | None = None

    # Export tracking
    export_format: str | None = None
    export_destination: str | None = None

    # Timing and status
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    duration_ms: int = 0
    status: str = "success"
    error_code: str | None = None

    # Compliance tags
    compliance_flags: list[str] = field(default_factory=list)
```

### Frontend Integration (Design Review - Enhanced)

#### Navigation

```jsx
// Add to CollapsibleSidebar
{
  icon: DocumentTextIcon,  // Heroicon, not emoji
  label: 'Documentation',
  path: '/documentation',
  children: [
    { label: 'Architecture Diagrams', path: '/documentation/diagrams' },
    { label: 'System Reports', path: '/documentation/reports' },
    { label: 'Data Flow', path: '/documentation/data-flow' },
  ]
}
```

#### Confidence Visualization (Color + Border, Not Percentages)

```jsx
// Confidence indicator component
const ConfidenceIndicator = ({ level }) => {
  const styles = {
    verified: "border-success border-2 opacity-100",
    high: "border-primary border-2 opacity-100",
    medium: "border-medium border-dashed border-2 opacity-90",
    low: "border-high border-dashed border-2 opacity-70",
    uncertain: "border-critical border-dotted animate-pulse opacity-60",
  };

  return (
    <div className={`${styles[level]} rounded-lg p-2`}>
      {/* Content */}
    </div>
  );
};
```

#### Accessibility Requirements (WCAG 2.1 AA)

```jsx
// Keyboard navigation for diagram viewer
const keyboardHandlers = {
  Tab: "Move focus between diagram nodes",
  ArrowKeys: "Navigate between connected nodes",
  Enter: "Open detail panel for focused node",
  Space: "Toggle node selection",
  Escape: "Close detail panel, exit diagram focus",
  "Ctrl+F": "Open search within diagram",
};

// ARIA labels for diagram nodes
<g
  role="button"
  tabIndex={0}
  aria-label={`${node.label}, ${node.type}, confidence ${node.confidenceLevel}`}
  aria-describedby={`node-${node.id}-description`}
>
```

#### Click-to-Code Interaction Flow

```
1. Hover on diagram node (300ms delay)
   - Border: 2px solid #3B82F6
   - Tooltip: "Click to view source"

2. Single Click
   - Node pulses (scale 1.02, 150ms)
   - Right panel slides in (320px, 250ms)
   - Shows: file path, code snippet, "Open in Editor" button

3. Double Click
   - Opens file in integrated code viewer
   - Diagram collapses to 60% width

4. Escape
   - Closes detail panel
   - Returns focus to diagram
```

#### Required UI States

1. **Empty State:** "No Documentation Generated Yet" with illustration and CTA
2. **Loading State:** Skeleton screen with progress stages
3. **Error State:** User-friendly message with "Try Again" and "View Status" buttons
4. **Partial Result State:** Warning banner with available data

### Implementation Phases

#### Phase 1: Code-Derived Architecture (8-10 weeks)

| Component | Effort | Dependencies |
|-----------|--------|--------------|
| Exception hierarchy and types | 1 week | None |
| DocumentationAgent core | 3 weeks | Existing GraphRAG |
| Service boundary detector (Louvain) | 2 weeks | Neptune queries |
| Diagram generator (Mermaid) | 2 weeks | None |
| Report generator | 2 weeks | Diagram generator |
| Frontend integration | 1 week | Existing UI framework |

**Deliverables:**
- Component diagrams from code structure
- Dependency graphs from imports
- Class diagrams from OOP patterns
- System overview reports
- Confidence-scored findings

#### Phase 1.5: Calibration Infrastructure (2 weeks)

| Component | Effort | Dependencies |
|-----------|--------|--------------|
| Confidence calibration service | 1 week | Phase 1 |
| Feedback collection UI | 0.5 week | Phase 1 |
| Correction storage for few-shot | 0.5 week | Phase 1 |

#### Phase 2: Cloud Infrastructure Correlation (6-8 weeks)

**Prerequisite:** Security design review for credential management

| Component | Effort | Dependencies |
|-----------|--------|--------------|
| Credential proxy service | 2 weeks | Secrets Manager |
| AWS discovery provider | 2 weeks | boto3, credential proxy |
| Azure discovery provider | 2 weeks | azure-identity |
| Cross-account role assumption | 1 week | IAM setup |
| IaC correlation engine | 2 weeks | Phase 1 |
| Circuit breaker pattern | 0.5 week | Discovery providers |
| GovCloud compatibility | 0.5 week | All providers |

#### Phase 3: Data Flow Analysis (4-6 weeks)

| Component | Effort | Dependencies |
|-----------|--------|--------------|
| Database connection tracing | 2 weeks | Phase 1 |
| Queue/event flow analysis | 1 week | Phase 1 |
| API call chain tracing | 1 week | Phase 1 |
| PII/sensitive data detection | 1 week | Existing secrets scanner |
| Data flow reports | 1 week | All above |

#### Phase 4: Interactive Documentation (4 weeks)

| Component | Effort | Dependencies |
|-----------|--------|--------------|
| Interactive diagram viewer (D3.js) | 2 weeks | Phase 1 |
| Click-to-code navigation | 1 week | Existing file viewer |
| Manual annotations | 1 week | Diagram viewer |
| Accessibility (keyboard nav, ARIA) | 1 week | All UI components |

### Storage Architecture (Tyler's Review)

#### DynamoDB Table Design

```yaml
Table: aura-documentation-artifacts
  PK: repository_id
  SK: artifact_type#artifact_id

  GSI1: artifact_type-created_at-index
    PK: artifact_type
    SK: created_at

  GSI2: repository_id-updated_at-index
    PK: repository_id
    SK: updated_at
```

#### S3 Bucket Structure

```
s3://aura-documentation-{environment}/
  {organization_id}/
    {repository_id}/
      diagrams/
        {diagram_id}.svg
        {diagram_id}.png
        {diagram_id}.pdf
      reports/
        {report_id}/
          report.pdf
          assets/
      exports/
        {export_id}.zip
```

### Success Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| Diagram accuracy (user validation) | >85% elements correct | Post-generation survey |
| Time savings vs. manual | >80% reduction | Comparison study |
| Expected Calibration Error | <0.05 (within 5%) | Predicted vs. validated confidence |
| User adoption | >50% of repos have generated docs | Dashboard metrics |
| Report usefulness | >4.0/5.0 rating | User feedback |

---

## Consequences

### Positive

1. **Dramatic time savings** - Hours/days instead of weeks for system understanding
2. **Consistent documentation** - Standardized diagrams across all repositories
3. **Living documentation** - Diagrams update as code changes
4. **Confidence transparency** - Users know what's certain vs. inferred
5. **Compliance support** - Automated architecture diagram generation for audits
6. **Onboarding acceleration** - New team members get instant system context
7. **Self-improving accuracy** - Feedback loop improves calibration over time

### Negative

1. **False confidence risk** - Users may over-trust generated diagrams
2. **Maintenance burden** - New agent to maintain and evolve
3. **Cloud credential scope** - Broader access required for discovery (Phase 2)
4. **Compute cost** - Graph traversal and diagram generation are resource-intensive

### Mitigations

| Risk | Mitigation |
|------|------------|
| False confidence | Prominent confidence visualization, "needs validation" flags, calibration system |
| Maintenance burden | Leverage existing GraphRAG infrastructure, reuse BaseAgent patterns |
| Credential scope | Credential proxy, separation of duties, read-only policies, rotation |
| Compute cost | 3-tier caching, incremental updates, background generation |

---

## References

- ADR-024: Titan Neural Memory Architecture
- ADR-034: Context Engineering Framework
- ADR-037: AWS Agent Parity
- ADR-043: Repository Onboarding Wizard
- ADR-048: Developer Tools and Data Platform Integrations
- Stripe Developer Coefficient Report (2023)
- Mermaid.js Documentation
- D2 Diagram Language Specification
- NetworkX Louvain Community Detection
- Isotonic Regression for Confidence Calibration
