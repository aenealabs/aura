"""
Architecture Reimaginer - AWS Transform Agent Parity

Intelligent architecture modernization and redesign recommendations.
Analyzes legacy architectures and proposes modern cloud-native patterns,
microservices decomposition, and serverless opportunities.

Reference: ADR-030 Section 5.4 Transform Agent Components
"""

import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class ArchitectureStyle(str, Enum):
    """Architecture styles."""

    MONOLITH = "monolith"
    MODULAR_MONOLITH = "modular_monolith"
    SOA = "soa"
    MICROSERVICES = "microservices"
    SERVERLESS = "serverless"
    EVENT_DRIVEN = "event_driven"
    CQRS = "cqrs"
    HEXAGONAL = "hexagonal"
    LAYERED = "layered"


class CloudProvider(str, Enum):
    """Target cloud providers."""

    AWS = "aws"
    AZURE = "azure"
    GCP = "gcp"
    MULTI_CLOUD = "multi_cloud"
    ON_PREMISE = "on_premise"
    HYBRID = "hybrid"


class ModernizationStrategy(str, Enum):
    """Application modernization strategies (6 Rs)."""

    REHOST = "rehost"
    REPLATFORM = "replatform"
    REPURCHASE = "repurchase"
    REFACTOR = "refactor"
    RETIRE = "retire"
    RETAIN = "retain"


class ComponentType(str, Enum):
    """System component types."""

    WEB_FRONTEND = "web_frontend"
    API_GATEWAY = "api_gateway"
    BACKEND_SERVICE = "backend_service"
    DATABASE = "database"
    CACHE = "cache"
    MESSAGE_QUEUE = "message_queue"
    FILE_STORAGE = "file_storage"
    BATCH_PROCESSOR = "batch_processor"
    SCHEDULER = "scheduler"
    AUTHENTICATION = "authentication"
    LOGGING = "logging"
    MONITORING = "monitoring"
    CDN = "cdn"
    LOAD_BALANCER = "load_balancer"
    SEARCH_ENGINE = "search_engine"


class DatabaseType(str, Enum):
    """Database types."""

    RELATIONAL = "relational"
    DOCUMENT = "document"
    KEY_VALUE = "key_value"
    GRAPH = "graph"
    TIME_SERIES = "time_series"
    WIDE_COLUMN = "wide_column"
    SEARCH = "search"


class CommunicationPattern(str, Enum):
    """Service communication patterns."""

    SYNCHRONOUS_HTTP = "synchronous_http"
    SYNCHRONOUS_GRPC = "synchronous_grpc"
    ASYNCHRONOUS_MESSAGING = "asynchronous_messaging"
    EVENT_STREAMING = "event_streaming"
    WEBSOCKET = "websocket"
    GRAPHQL = "graphql"


class ScalabilityPattern(str, Enum):
    """Scalability patterns."""

    HORIZONTAL = "horizontal"
    VERTICAL = "vertical"
    AUTO_SCALING = "auto_scaling"
    LOAD_SHEDDING = "load_shedding"
    CIRCUIT_BREAKER = "circuit_breaker"
    BULKHEAD = "bulkhead"
    RATE_LIMITING = "rate_limiting"


class DataConsistencyPattern(str, Enum):
    """Data consistency patterns."""

    STRONG = "strong"
    EVENTUAL = "eventual"
    SAGA = "saga"
    TWO_PHASE_COMMIT = "two_phase_commit"
    OUTBOX = "outbox"
    CDC = "cdc"


class DeploymentPattern(str, Enum):
    """Deployment patterns."""

    CONTAINER = "container"
    SERVERLESS_FUNCTION = "serverless_function"
    VM = "vm"
    KUBERNETES = "kubernetes"
    ECS = "ecs"
    APP_SERVICE = "app_service"


class RiskLevel(str, Enum):
    """Migration risk levels."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class Priority(str, Enum):
    """Implementation priority."""

    IMMEDIATE = "immediate"
    SHORT_TERM = "short_term"
    MEDIUM_TERM = "medium_term"
    LONG_TERM = "long_term"


@dataclass
class TechnologyStack:
    """Technology stack definition."""

    name: str
    version: str | None = None
    category: str = ""
    is_legacy: bool = False
    end_of_life: datetime | None = None
    modern_alternative: str | None = None


@dataclass
class SystemComponent:
    """System component definition."""

    id: str
    name: str
    component_type: ComponentType
    technology_stack: list[TechnologyStack] = field(default_factory=list)
    dependencies: list[str] = field(default_factory=list)
    dependents: list[str] = field(default_factory=list)
    responsibilities: list[str] = field(default_factory=list)
    data_entities: list[str] = field(default_factory=list)
    estimated_lines_of_code: int = 0
    team_ownership: str = ""
    change_frequency: str = "low"
    business_criticality: str = "medium"


@dataclass
class DataStore:
    """Data store definition."""

    id: str
    name: str
    database_type: DatabaseType
    technology: str
    size_gb: float = 0
    tables_count: int = 0
    read_qps: float = 0
    write_qps: float = 0
    consistency_requirement: DataConsistencyPattern = DataConsistencyPattern.STRONG


@dataclass
class Integration:
    """External integration definition."""

    id: str
    name: str
    system: str
    protocol: str
    direction: str
    data_format: str
    frequency: str
    criticality: str = "medium"


@dataclass
class CurrentArchitecture:
    """Current system architecture."""

    name: str
    style: ArchitectureStyle
    components: list[SystemComponent] = field(default_factory=list)
    data_stores: list[DataStore] = field(default_factory=list)
    integrations: list[Integration] = field(default_factory=list)
    deployment_environment: str = ""
    total_users: int = 0
    peak_transactions_per_second: float = 0
    availability_sla: float = 99.0
    documentation_quality: str = "low"


@dataclass
class MicroserviceCandidate:
    """Candidate microservice from decomposition."""

    id: str
    name: str
    bounded_context: str
    responsibilities: list[str] = field(default_factory=list)
    data_entities: list[str] = field(default_factory=list)
    source_components: list[str] = field(default_factory=list)
    api_endpoints: list[str] = field(default_factory=list)
    database_type: DatabaseType = DatabaseType.RELATIONAL
    estimated_team_size: int = 1
    deployment_pattern: DeploymentPattern = DeploymentPattern.CONTAINER


@dataclass
class ServiceDecomposition:
    """Microservice decomposition result."""

    microservices: list[MicroserviceCandidate] = field(default_factory=list)
    shared_services: list[MicroserviceCandidate] = field(default_factory=list)
    data_migration_plan: list[str] = field(default_factory=list)
    strangler_fig_sequence: list[str] = field(default_factory=list)
    estimated_total_services: int = 0


@dataclass
class CloudServiceMapping:
    """Mapping from current component to cloud service."""

    source_component: str
    target_service: str
    cloud_provider: CloudProvider
    service_category: str
    rationale: str
    estimated_cost_monthly: float = 0
    migration_complexity: str = "medium"


@dataclass
class InfrastructureRecommendation:
    """Infrastructure recommendation."""

    category: str
    current_state: str
    recommended_state: str
    cloud_services: list[CloudServiceMapping] = field(default_factory=list)
    benefits: list[str] = field(default_factory=list)
    implementation_steps: list[str] = field(default_factory=list)
    estimated_cost_impact: str = ""


@dataclass
class SecurityRecommendation:
    """Security improvement recommendation."""

    category: str
    finding: str
    recommendation: str
    implementation: str
    priority: Priority = Priority.MEDIUM_TERM
    compliance_frameworks: list[str] = field(default_factory=list)


@dataclass
class MigrationRisk:
    """Migration risk assessment."""

    category: str
    description: str
    level: RiskLevel
    mitigation_strategy: str
    affected_components: list[str] = field(default_factory=list)


@dataclass
class MigrationPhase:
    """Migration phase definition."""

    name: str
    description: str
    order: int
    components: list[str] = field(default_factory=list)
    dependencies: list[str] = field(default_factory=list)
    estimated_duration_weeks: int = 0
    team_requirements: dict[str, int] = field(default_factory=dict)
    success_criteria: list[str] = field(default_factory=list)
    rollback_strategy: str = ""


@dataclass
class MigrationRoadmap:
    """Complete migration roadmap."""

    phases: list[MigrationPhase] = field(default_factory=list)
    total_duration_weeks: int = 0
    estimated_total_cost: float = 0
    quick_wins: list[str] = field(default_factory=list)
    parallel_tracks: list[list[str]] = field(default_factory=list)


@dataclass
class ArchitecturePattern:
    """Recommended architecture pattern."""

    name: str
    description: str
    applicability: list[str] = field(default_factory=list)
    benefits: list[str] = field(default_factory=list)
    tradeoffs: list[str] = field(default_factory=list)
    implementation_guidance: str = ""
    related_patterns: list[str] = field(default_factory=list)


@dataclass
class TargetArchitecture:
    """Proposed target architecture."""

    name: str
    style: ArchitectureStyle
    cloud_provider: CloudProvider
    decomposition: ServiceDecomposition | None = None
    infrastructure: list[InfrastructureRecommendation] = field(default_factory=list)
    patterns: list[ArchitecturePattern] = field(default_factory=list)
    security_recommendations: list[SecurityRecommendation] = field(default_factory=list)
    migration_roadmap: MigrationRoadmap | None = None
    risks: list[MigrationRisk] = field(default_factory=list)
    estimated_cost_reduction_percent: float = 0
    estimated_performance_improvement_percent: float = 0


@dataclass
class ArchitectureAssessment:
    """Complete architecture assessment."""

    id: str
    name: str
    current_architecture: CurrentArchitecture
    target_architecture: TargetArchitecture
    modernization_strategy: ModernizationStrategy
    business_case: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    assessment_hash: str = ""


class ArchitectureReimaginer:
    """
    Architecture reimaginer for legacy modernization.

    Analyzes existing architectures and proposes modern transformations:
    - Microservice decomposition using domain-driven design
    - Cloud service mapping and recommendations
    - Migration planning with strangler fig pattern
    - Infrastructure modernization
    - Security improvements

    Supports AWS, Azure, and GCP target platforms.
    """

    def __init__(self) -> None:
        """Initialize architecture reimaginer."""
        self._cloud_service_mappings = self._build_cloud_service_mappings()
        self._architecture_patterns = self._build_architecture_patterns()
        self._technology_modernization_map = self._build_technology_modernization_map()

    def _build_cloud_service_mappings(self) -> dict[CloudProvider, dict[str, str]]:
        """Build cloud service mappings for common components."""
        return {
            CloudProvider.AWS: {
                "web_frontend": "AWS Amplify / CloudFront + S3",
                "api_gateway": "Amazon API Gateway",
                "backend_service": "AWS Lambda / ECS / EKS",
                "relational_database": "Amazon RDS / Aurora",
                "document_database": "Amazon DocumentDB",
                "key_value_database": "Amazon DynamoDB",
                "cache": "Amazon ElastiCache",
                "message_queue": "Amazon SQS",
                "event_streaming": "Amazon Kinesis / MSK",
                "file_storage": "Amazon S3",
                "batch_processor": "AWS Batch / Step Functions",
                "scheduler": "Amazon EventBridge",
                "authentication": "Amazon Cognito",
                "logging": "Amazon CloudWatch Logs",
                "monitoring": "Amazon CloudWatch",
                "cdn": "Amazon CloudFront",
                "load_balancer": "Application Load Balancer",
                "search_engine": "Amazon OpenSearch",
                "secrets": "AWS Secrets Manager",
                "container_registry": "Amazon ECR",
                "dns": "Amazon Route 53",
            },
            CloudProvider.AZURE: {
                "web_frontend": "Azure Static Web Apps",
                "api_gateway": "Azure API Management",
                "backend_service": "Azure Functions / AKS / App Service",
                "relational_database": "Azure SQL Database / PostgreSQL",
                "document_database": "Azure Cosmos DB",
                "key_value_database": "Azure Cosmos DB",
                "cache": "Azure Cache for Redis",
                "message_queue": "Azure Service Bus",
                "event_streaming": "Azure Event Hubs",
                "file_storage": "Azure Blob Storage",
                "batch_processor": "Azure Batch / Logic Apps",
                "scheduler": "Azure Logic Apps",
                "authentication": "Azure AD B2C",
                "logging": "Azure Monitor Logs",
                "monitoring": "Azure Monitor",
                "cdn": "Azure CDN",
                "load_balancer": "Azure Load Balancer",
                "search_engine": "Azure Cognitive Search",
                "secrets": "Azure Key Vault",
                "container_registry": "Azure Container Registry",
                "dns": "Azure DNS",
            },
            CloudProvider.GCP: {
                "web_frontend": "Firebase Hosting",
                "api_gateway": "Cloud Endpoints / Apigee",
                "backend_service": "Cloud Functions / Cloud Run / GKE",
                "relational_database": "Cloud SQL / Cloud Spanner",
                "document_database": "Firestore",
                "key_value_database": "Cloud Bigtable",
                "cache": "Memorystore",
                "message_queue": "Cloud Pub/Sub",
                "event_streaming": "Cloud Pub/Sub",
                "file_storage": "Cloud Storage",
                "batch_processor": "Cloud Dataflow / Workflows",
                "scheduler": "Cloud Scheduler",
                "authentication": "Identity Platform",
                "logging": "Cloud Logging",
                "monitoring": "Cloud Monitoring",
                "cdn": "Cloud CDN",
                "load_balancer": "Cloud Load Balancing",
                "search_engine": "Elastic Cloud on GCP",
                "secrets": "Secret Manager",
                "container_registry": "Artifact Registry",
                "dns": "Cloud DNS",
            },
        }

    def _build_architecture_patterns(self) -> dict[str, ArchitecturePattern]:
        """Build catalog of architecture patterns."""
        return {
            "api_gateway": ArchitecturePattern(
                name="API Gateway",
                description="Single entry point for all client requests",
                applicability=["microservices", "multi-client", "legacy_integration"],
                benefits=[
                    "Centralized authentication",
                    "Rate limiting",
                    "Request routing",
                    "Protocol translation",
                ],
                tradeoffs=[
                    "Single point of failure",
                    "Additional latency",
                    "Increased complexity",
                ],
                related_patterns=["backends_for_frontends", "service_mesh"],
            ),
            "backends_for_frontends": ArchitecturePattern(
                name="Backends for Frontends (BFF)",
                description="Separate backends for different frontend applications",
                applicability=[
                    "multiple_frontends",
                    "mobile_web",
                    "different_requirements",
                ],
                benefits=[
                    "Optimized for specific frontend",
                    "Independent evolution",
                    "Reduced complexity per frontend",
                ],
                tradeoffs=["Code duplication", "More services to maintain"],
                related_patterns=["api_gateway", "microservices"],
            ),
            "saga": ArchitecturePattern(
                name="Saga Pattern",
                description="Manage distributed transactions across microservices",
                applicability=["distributed_transactions", "eventual_consistency"],
                benefits=[
                    "No distributed locks",
                    "Better availability",
                    "Service autonomy",
                ],
                tradeoffs=[
                    "Complex error handling",
                    "Eventual consistency",
                    "Compensating transactions",
                ],
                related_patterns=["cqrs", "event_sourcing"],
            ),
            "cqrs": ArchitecturePattern(
                name="CQRS",
                description="Separate read and write models",
                applicability=[
                    "high_read_write_ratio",
                    "complex_domain",
                    "event_sourcing",
                ],
                benefits=["Optimized read models", "Scalability", "Simpler queries"],
                tradeoffs=[
                    "Increased complexity",
                    "Eventual consistency",
                    "More infrastructure",
                ],
                related_patterns=["event_sourcing", "saga"],
            ),
            "event_sourcing": ArchitecturePattern(
                name="Event Sourcing",
                description="Store state changes as events",
                applicability=[
                    "audit_requirements",
                    "temporal_queries",
                    "event_driven",
                ],
                benefits=[
                    "Complete audit trail",
                    "Temporal queries",
                    "Replay capability",
                ],
                tradeoffs=["Storage growth", "Query complexity", "Event versioning"],
                related_patterns=["cqrs", "saga"],
            ),
            "strangler_fig": ArchitecturePattern(
                name="Strangler Fig",
                description="Incrementally migrate legacy systems",
                applicability=[
                    "legacy_migration",
                    "risk_reduction",
                    "continuous_operation",
                ],
                benefits=["Gradual migration", "Reduced risk", "Continuous operation"],
                tradeoffs=[
                    "Longer timeline",
                    "Temporary complexity",
                    "Multiple systems in parallel",
                ],
                related_patterns=["anti_corruption_layer"],
            ),
            "anti_corruption_layer": ArchitecturePattern(
                name="Anti-Corruption Layer",
                description="Isolate new system from legacy interfaces",
                applicability=["legacy_integration", "domain_protection", "migration"],
                benefits=[
                    "Clean domain model",
                    "Legacy isolation",
                    "Gradual transition",
                ],
                tradeoffs=[
                    "Additional translation",
                    "Performance overhead",
                    "Maintenance burden",
                ],
                related_patterns=["strangler_fig", "adapter"],
            ),
            "circuit_breaker": ArchitecturePattern(
                name="Circuit Breaker",
                description="Prevent cascading failures in distributed systems",
                applicability=["distributed_systems", "resilience", "fault_tolerance"],
                benefits=[
                    "Fail fast",
                    "Prevent cascading failures",
                    "Automatic recovery",
                ],
                tradeoffs=[
                    "Additional complexity",
                    "Configuration tuning",
                    "False positives",
                ],
                related_patterns=["bulkhead", "retry"],
            ),
            "sidecar": ArchitecturePattern(
                name="Sidecar",
                description="Deploy auxiliary components alongside main service",
                applicability=["cross_cutting_concerns", "polyglot", "service_mesh"],
                benefits=[
                    "Language agnostic",
                    "Separation of concerns",
                    "Consistent infrastructure",
                ],
                tradeoffs=["Resource overhead", "Latency", "Operational complexity"],
                related_patterns=["service_mesh", "ambassador"],
            ),
        }

    def _build_technology_modernization_map(self) -> dict[str, dict[str, Any]]:
        """Build technology modernization recommendations."""
        return {
            "Oracle": {
                "alternatives": [
                    "PostgreSQL",
                    "Amazon Aurora PostgreSQL",
                    "CockroachDB",
                ],
                "rationale": "Cost reduction, open source, cloud-native options",
                "migration_complexity": "high",
            },
            "SQL Server": {
                "alternatives": ["PostgreSQL", "Amazon Aurora PostgreSQL", "Azure SQL"],
                "rationale": "Licensing cost, portability, cloud-native",
                "migration_complexity": "medium",
            },
            "WebSphere": {
                "alternatives": ["Spring Boot", "Quarkus", "AWS Lambda"],
                "rationale": "Licensing, modernization, containerization",
                "migration_complexity": "high",
            },
            "WebLogic": {
                "alternatives": ["Spring Boot", "Quarkus", "AWS Lambda"],
                "rationale": "Licensing, modernization, containerization",
                "migration_complexity": "high",
            },
            "JBoss": {
                "alternatives": ["Spring Boot", "Quarkus", "WildFly"],
                "rationale": "Modernization, containerization",
                "migration_complexity": "medium",
            },
            "COBOL": {
                "alternatives": ["Java", "Python", "Go"],
                "rationale": "Talent availability, maintainability, cloud-native",
                "migration_complexity": "very_high",
            },
            ".NET Framework": {
                "alternatives": [".NET 8", ".NET MAUI", "ASP.NET Core"],
                "rationale": "Cross-platform, performance, modern features",
                "migration_complexity": "medium",
            },
            "WCF": {
                "alternatives": ["gRPC", "REST API", "GraphQL"],
                "rationale": "Modern protocols, cross-platform, performance",
                "migration_complexity": "medium",
            },
            "SOAP": {
                "alternatives": ["REST", "GraphQL", "gRPC"],
                "rationale": "Simplicity, performance, tooling",
                "migration_complexity": "low",
            },
            "Monolithic Deployment": {
                "alternatives": ["Containers", "Kubernetes", "Serverless"],
                "rationale": "Scalability, resilience, cost optimization",
                "migration_complexity": "medium",
            },
        }

    async def analyze_architecture(
        self,
        current: CurrentArchitecture,
        target_cloud: CloudProvider = CloudProvider.AWS,
        preferred_strategy: ModernizationStrategy | None = None,
    ) -> ArchitectureAssessment:
        """
        Analyze current architecture and generate modernization recommendations.

        Args:
            current: Current architecture definition
            target_cloud: Target cloud provider
            preferred_strategy: Preferred modernization strategy

        Returns:
            Complete architecture assessment with recommendations
        """
        # Generate assessment ID
        assessment_id = hashlib.sha256(
            f"{current.name}_{datetime.now(timezone.utc).isoformat()}".encode()
        ).hexdigest()[:12]

        # Determine best modernization strategy if not specified
        if not preferred_strategy:
            preferred_strategy = self._recommend_strategy(current)

        # Analyze and decompose
        decomposition = None
        if preferred_strategy == ModernizationStrategy.REFACTOR:
            decomposition = await self._decompose_to_microservices(current)

        # Generate infrastructure recommendations
        infrastructure = await self._generate_infrastructure_recommendations(
            current, target_cloud
        )

        # Identify applicable patterns
        patterns = self._identify_applicable_patterns(current, preferred_strategy)

        # Security recommendations
        security = self._generate_security_recommendations(current)

        # Risk assessment
        risks = self._assess_migration_risks(current, preferred_strategy)

        # Generate migration roadmap
        roadmap = await self._generate_migration_roadmap(
            current, decomposition, preferred_strategy
        )

        # Calculate estimates
        cost_reduction = self._estimate_cost_reduction(current, target_cloud)
        perf_improvement = self._estimate_performance_improvement(
            current, preferred_strategy
        )

        # Build target architecture
        target_style = self._determine_target_style(current, preferred_strategy)

        target = TargetArchitecture(
            name=f"{current.name} - Modernized",
            style=target_style,
            cloud_provider=target_cloud,
            decomposition=decomposition,
            infrastructure=infrastructure,
            patterns=patterns,
            security_recommendations=security,
            migration_roadmap=roadmap,
            risks=risks,
            estimated_cost_reduction_percent=cost_reduction,
            estimated_performance_improvement_percent=perf_improvement,
        )

        # Build business case
        business_case = self._build_business_case(current, target, roadmap)

        # Create assessment
        assessment = ArchitectureAssessment(
            id=assessment_id,
            name=f"Assessment: {current.name}",
            current_architecture=current,
            target_architecture=target,
            modernization_strategy=preferred_strategy,
            business_case=business_case,
        )

        # Generate hash for change tracking
        assessment.assessment_hash = hashlib.sha256(
            str(assessment.__dict__).encode()
        ).hexdigest()[:16]

        return assessment

    def _recommend_strategy(
        self, current: CurrentArchitecture
    ) -> ModernizationStrategy:
        """Recommend modernization strategy based on current state."""
        # Check for legacy factors
        legacy_components = sum(
            1 for c in current.components for t in c.technology_stack if t.is_legacy
        )
        total_components = len(current.components)

        # Check complexity
        high_coupling = self._calculate_coupling(current) > 0.7
        documentation_poor = current.documentation_quality == "low"

        # Decision logic
        if legacy_components == 0 and not high_coupling:
            return ModernizationStrategy.REPLATFORM
        elif legacy_components / max(total_components, 1) > 0.5:
            if documentation_poor:
                return ModernizationStrategy.REHOST
            return ModernizationStrategy.REFACTOR
        elif high_coupling:
            return ModernizationStrategy.REFACTOR
        else:
            return ModernizationStrategy.REPLATFORM

    def _calculate_coupling(self, current: CurrentArchitecture) -> float:
        """Calculate coupling coefficient."""
        if not current.components:
            return 0.0

        total_deps = sum(len(c.dependencies) for c in current.components)
        max_possible = len(current.components) * (len(current.components) - 1)

        if max_possible == 0:
            return 0.0

        return total_deps / max_possible

    async def _decompose_to_microservices(
        self, current: CurrentArchitecture
    ) -> ServiceDecomposition:
        """Decompose monolith to microservices using DDD principles."""
        decomposition = ServiceDecomposition()

        # Identify bounded contexts from components
        bounded_contexts = self._identify_bounded_contexts(current)

        # Create microservice candidates for each bounded context
        for bc_name, bc_components in bounded_contexts.items():
            # Aggregate data entities
            entities = set()
            responsibilities = []
            source_ids = []

            for comp in bc_components:
                entities.update(comp.data_entities)
                responsibilities.extend(comp.responsibilities)
                source_ids.append(comp.id)

            # Determine database type
            db_type = self._recommend_database_type(list(entities), bc_name)

            # Determine deployment pattern
            deploy_pattern = self._recommend_deployment_pattern(bc_components)

            microservice = MicroserviceCandidate(
                id=f"svc-{bc_name.lower().replace(' ', '-')}",
                name=f"{bc_name} Service",
                bounded_context=bc_name,
                responsibilities=list(set(responsibilities)),
                data_entities=list(entities),
                source_components=source_ids,
                database_type=db_type,
                deployment_pattern=deploy_pattern,
                estimated_team_size=self._estimate_team_size(bc_components),
            )

            decomposition.microservices.append(microservice)

        # Identify shared services
        decomposition.shared_services = self._identify_shared_services(current)

        # Generate data migration plan
        decomposition.data_migration_plan = self._generate_data_migration_plan(
            current, decomposition.microservices
        )

        # Generate strangler fig sequence
        decomposition.strangler_fig_sequence = self._generate_strangler_sequence(
            decomposition.microservices
        )

        decomposition.estimated_total_services = len(decomposition.microservices) + len(
            decomposition.shared_services
        )

        return decomposition

    def _identify_bounded_contexts(
        self, current: CurrentArchitecture
    ) -> dict[str, list[SystemComponent]]:
        """Identify bounded contexts from components."""
        contexts: dict[str, list[SystemComponent]] = {}

        for component in current.components:
            # Use team ownership as initial context boundary
            context_name = component.team_ownership or "Core"

            # Refine by business criticality
            if component.business_criticality == "critical":
                context_name = f"Critical {context_name}"

            if context_name not in contexts:
                contexts[context_name] = []
            contexts[context_name].append(component)

        return contexts

    def _recommend_database_type(
        self, entities: list[str], context_name: str
    ) -> DatabaseType:
        """Recommend database type for bounded context."""
        # Simple heuristics
        entity_names_lower = [e.lower() for e in entities]

        if any("transaction" in e or "order" in e for e in entity_names_lower):
            return DatabaseType.RELATIONAL
        elif any("log" in e or "event" in e for e in entity_names_lower):
            return DatabaseType.TIME_SERIES
        elif any("document" in e or "content" in e for e in entity_names_lower):
            return DatabaseType.DOCUMENT
        elif any("session" in e or "cache" in e for e in entity_names_lower):
            return DatabaseType.KEY_VALUE
        elif any("relationship" in e or "graph" in e for e in entity_names_lower):
            return DatabaseType.GRAPH

        return DatabaseType.RELATIONAL

    def _recommend_deployment_pattern(
        self, components: list[SystemComponent]
    ) -> DeploymentPattern:
        """Recommend deployment pattern for service."""
        # Check characteristics
        total_loc = sum(c.estimated_lines_of_code for c in components)
        is_batch = any(
            c.component_type == ComponentType.BATCH_PROCESSOR for c in components
        )
        change_freq = any(c.change_frequency == "high" for c in components)

        if is_batch and total_loc < 5000:
            return DeploymentPattern.SERVERLESS_FUNCTION
        elif change_freq and total_loc < 10000:
            return DeploymentPattern.SERVERLESS_FUNCTION
        elif total_loc > 50000:
            return DeploymentPattern.KUBERNETES

        return DeploymentPattern.CONTAINER

    def _estimate_team_size(self, components: list[SystemComponent]) -> int:
        """Estimate team size for microservice."""
        total_loc = sum(c.estimated_lines_of_code for c in components)

        if total_loc < 10000:
            return 2
        elif total_loc < 50000:
            return 4
        elif total_loc < 100000:
            return 6
        return 8

    def _identify_shared_services(
        self, current: CurrentArchitecture
    ) -> list[MicroserviceCandidate]:
        """Identify shared/cross-cutting services."""
        shared = []

        # Always recommend these shared services
        shared_patterns = [
            ("authentication", "Auth Service", ["authentication", "authorization"]),
            ("logging", "Logging Service", ["centralized logging", "audit"]),
            ("monitoring", "Observability Service", ["metrics", "tracing", "alerting"]),
            ("api_gateway", "API Gateway", ["routing", "rate limiting", "auth"]),
        ]

        for service_type, name, responsibilities in shared_patterns:
            shared.append(
                MicroserviceCandidate(
                    id=f"shared-{service_type}",
                    name=name,
                    bounded_context="Shared",
                    responsibilities=responsibilities,
                    deployment_pattern=DeploymentPattern.CONTAINER,
                )
            )

        return shared

    def _generate_data_migration_plan(
        self, current: CurrentArchitecture, microservices: list[MicroserviceCandidate]
    ) -> list[str]:
        """Generate data migration plan."""
        plan = []

        plan.append("1. Assess current data dependencies and ownership")
        plan.append("2. Create database-per-service instances")

        for i, svc in enumerate(microservices, 3):
            plan.append(
                f"{i}. Migrate {', '.join(svc.data_entities[:3])} to {svc.name}"
            )

        plan.append(
            f"{len(microservices) + 3}. Implement data synchronization for transition period"
        )
        plan.append(f"{len(microservices) + 4}. Validate data consistency")
        plan.append(f"{len(microservices) + 5}. Decommission legacy data access")

        return plan

    def _generate_strangler_sequence(
        self, microservices: list[MicroserviceCandidate]
    ) -> list[str]:
        """Generate strangler fig migration sequence."""
        # Sort by estimated complexity (simpler first)
        sorted_services = sorted(microservices, key=lambda s: len(s.source_components))

        sequence = []
        for i, svc in enumerate(sorted_services, 1):
            sequence.append(
                f"Phase {i}: Extract {svc.name} ({len(svc.source_components)} components)"
            )

        return sequence

    async def _generate_infrastructure_recommendations(
        self, current: CurrentArchitecture, target_cloud: CloudProvider
    ) -> list[InfrastructureRecommendation]:
        """Generate infrastructure modernization recommendations."""
        recommendations = []
        cloud_services = self._cloud_service_mappings.get(target_cloud, {})

        # Compute recommendations
        recommendations.append(
            InfrastructureRecommendation(
                category="Compute",
                current_state="Traditional VMs or on-premise servers",
                recommended_state="Container-based or serverless compute",
                cloud_services=[
                    CloudServiceMapping(
                        source_component="backend_services",
                        target_service=cloud_services.get(
                            "backend_service", "Containers"
                        ),
                        cloud_provider=target_cloud,
                        service_category="Compute",
                        rationale="Auto-scaling, cost optimization, operational efficiency",
                    )
                ],
                benefits=[
                    "Auto-scaling based on demand",
                    "Pay-per-use pricing",
                    "Reduced operational overhead",
                    "Faster deployments",
                ],
                implementation_steps=[
                    "Containerize applications using Docker",
                    "Set up container orchestration (EKS/ECS)",
                    "Implement CI/CD pipeline for containers",
                    "Configure auto-scaling policies",
                ],
            )
        )

        # Database recommendations
        for ds in current.data_stores:
            db_service = cloud_services.get(
                f"{ds.database_type.value}_database", "Managed Database"
            )

            recommendations.append(
                InfrastructureRecommendation(
                    category="Database",
                    current_state=f"{ds.technology} - Self-managed",
                    recommended_state=f"Managed {ds.database_type.value} service",
                    cloud_services=[
                        CloudServiceMapping(
                            source_component=ds.name,
                            target_service=db_service,
                            cloud_provider=target_cloud,
                            service_category="Database",
                            rationale="Managed service reduces operational burden",
                        )
                    ],
                    benefits=[
                        "Automated backups",
                        "High availability built-in",
                        "Automatic patching",
                        "Read replicas for scaling",
                    ],
                    implementation_steps=[
                        "Create managed database instance",
                        "Set up replication from current database",
                        "Validate data consistency",
                        "Perform cutover during maintenance window",
                    ],
                )
            )

        # Caching recommendations
        recommendations.append(
            InfrastructureRecommendation(
                category="Caching",
                current_state="Application-level caching or none",
                recommended_state="Distributed managed cache",
                cloud_services=[
                    CloudServiceMapping(
                        source_component="caching",
                        target_service=cloud_services.get("cache", "Managed Cache"),
                        cloud_provider=target_cloud,
                        service_category="Caching",
                        rationale="Improved performance and scalability",
                    )
                ],
                benefits=[
                    "Reduced database load",
                    "Lower latency",
                    "Session management",
                    "Shared cache across instances",
                ],
            )
        )

        # Messaging recommendations
        recommendations.append(
            InfrastructureRecommendation(
                category="Messaging",
                current_state="Synchronous communication or legacy messaging",
                recommended_state="Cloud-native messaging and event streaming",
                cloud_services=[
                    CloudServiceMapping(
                        source_component="messaging",
                        target_service=cloud_services.get(
                            "message_queue", "Message Queue"
                        ),
                        cloud_provider=target_cloud,
                        service_category="Messaging",
                        rationale="Decoupled architecture, reliability",
                    )
                ],
                benefits=[
                    "Service decoupling",
                    "Reliability through message persistence",
                    "Async processing",
                    "Event-driven architecture support",
                ],
            )
        )

        return recommendations

    def _identify_applicable_patterns(
        self, current: CurrentArchitecture, strategy: ModernizationStrategy
    ) -> list[ArchitecturePattern]:
        """Identify applicable architecture patterns."""
        patterns = []

        # Always recommend strangler fig for migration
        patterns.append(self._architecture_patterns["strangler_fig"])

        if strategy == ModernizationStrategy.REFACTOR:
            # Microservices patterns
            patterns.append(self._architecture_patterns["api_gateway"])
            patterns.append(self._architecture_patterns["circuit_breaker"])

            # If high transaction volume
            if current.peak_transactions_per_second > 1000:
                patterns.append(self._architecture_patterns["cqrs"])

            # Multiple frontend types
            if len(current.integrations) > 3:
                patterns.append(self._architecture_patterns["backends_for_frontends"])

            # Distributed transactions
            patterns.append(self._architecture_patterns["saga"])

        # Anti-corruption layer for legacy integration
        if current.style == ArchitectureStyle.MONOLITH:
            patterns.append(self._architecture_patterns["anti_corruption_layer"])

        return patterns

    def _generate_security_recommendations(
        self, current: CurrentArchitecture
    ) -> list[SecurityRecommendation]:
        """Generate security improvement recommendations."""
        recommendations = []

        recommendations.append(
            SecurityRecommendation(
                category="Identity & Access",
                finding="Centralized identity management needed",
                recommendation="Implement OAuth 2.0 / OIDC with managed identity provider",
                implementation="Use cloud-native identity service (Cognito/Azure AD/Identity Platform)",
                priority=Priority.IMMEDIATE,
                compliance_frameworks=["SOC2", "GDPR", "HIPAA"],
            )
        )

        recommendations.append(
            SecurityRecommendation(
                category="Network Security",
                finding="Network isolation improvements needed",
                recommendation="Implement zero-trust network architecture",
                implementation="Use VPCs, security groups, network policies, service mesh",
                priority=Priority.SHORT_TERM,
                compliance_frameworks=["SOC2", "PCI-DSS"],
            )
        )

        recommendations.append(
            SecurityRecommendation(
                category="Data Protection",
                finding="Data encryption at rest and in transit",
                recommendation="Enable encryption for all data stores and communication",
                implementation="Use managed encryption keys, TLS everywhere, encrypt at application layer for sensitive data",
                priority=Priority.IMMEDIATE,
                compliance_frameworks=["GDPR", "HIPAA", "PCI-DSS"],
            )
        )

        recommendations.append(
            SecurityRecommendation(
                category="Secrets Management",
                finding="Hardcoded secrets or config files",
                recommendation="Centralized secrets management",
                implementation="Use cloud secrets manager with automatic rotation",
                priority=Priority.IMMEDIATE,
                compliance_frameworks=["SOC2", "PCI-DSS"],
            )
        )

        recommendations.append(
            SecurityRecommendation(
                category="API Security",
                finding="API security controls needed",
                recommendation="Implement API gateway with security features",
                implementation="Use managed API gateway with authentication, rate limiting, WAF",
                priority=Priority.SHORT_TERM,
                compliance_frameworks=["OWASP API Security"],
            )
        )

        return recommendations

    def _assess_migration_risks(
        self, current: CurrentArchitecture, strategy: ModernizationStrategy
    ) -> list[MigrationRisk]:
        """Assess migration risks."""
        risks = []

        if strategy == ModernizationStrategy.REFACTOR:
            risks.append(
                MigrationRisk(
                    category="Technical",
                    description="Service decomposition may introduce distributed system complexity",
                    level=RiskLevel.HIGH,
                    mitigation_strategy="Start with well-bounded services, implement proper observability, use proven patterns",
                )
            )

            risks.append(
                MigrationRisk(
                    category="Data",
                    description="Data migration and consistency during transition",
                    level=RiskLevel.HIGH,
                    mitigation_strategy="Use CDC for sync, implement saga pattern, extensive testing",
                )
            )

        risks.append(
            MigrationRisk(
                category="Organizational",
                description="Team skills gap for cloud-native technologies",
                level=RiskLevel.MEDIUM,
                mitigation_strategy="Training programs, external expertise, gradual adoption",
            )
        )

        risks.append(
            MigrationRisk(
                category="Operational",
                description="Increased operational complexity during transition",
                level=RiskLevel.MEDIUM,
                mitigation_strategy="Implement comprehensive monitoring, runbooks, gradual cutover",
            )
        )

        if current.availability_sla > 99.9:
            risks.append(
                MigrationRisk(
                    category="Business",
                    description="High availability requirements may be impacted during migration",
                    level=RiskLevel.CRITICAL,
                    mitigation_strategy="Blue-green deployment, feature flags, extensive testing, off-peak migration windows",
                )
            )

        return risks

    async def _generate_migration_roadmap(
        self,
        current: CurrentArchitecture,
        decomposition: ServiceDecomposition | None,
        strategy: ModernizationStrategy,
    ) -> MigrationRoadmap:
        """Generate migration roadmap."""
        roadmap = MigrationRoadmap()

        # Phase 0: Foundation
        roadmap.phases.append(
            MigrationPhase(
                name="Foundation",
                description="Set up cloud infrastructure and CI/CD",
                order=0,
                estimated_duration_weeks=4,
                team_requirements={"platform": 2, "devops": 2},
                success_criteria=[
                    "Cloud accounts provisioned",
                    "VPC and networking configured",
                    "CI/CD pipeline operational",
                    "Monitoring and logging set up",
                ],
            )
        )

        # Phase 1: Quick Wins
        roadmap.phases.append(
            MigrationPhase(
                name="Quick Wins",
                description="Low-risk migrations and improvements",
                order=1,
                estimated_duration_weeks=2,
                team_requirements={"development": 4, "devops": 1},
                success_criteria=[
                    "Static assets moved to CDN",
                    "External integrations validated",
                    "Performance baselines established",
                ],
            )
        )
        roadmap.quick_wins = [
            "Move static assets to CDN",
            "Implement managed caching",
            "Set up centralized logging",
            "Enable infrastructure monitoring",
        ]

        if decomposition and strategy == ModernizationStrategy.REFACTOR:
            # Add phases for each service extraction
            for i, svc in enumerate(decomposition.microservices[:5], 2):
                roadmap.phases.append(
                    MigrationPhase(
                        name=f"Extract {svc.name}",
                        description=f"Extract {svc.bounded_context} bounded context",
                        order=i,
                        components=svc.source_components,
                        estimated_duration_weeks=4 + len(svc.source_components),
                        team_requirements={
                            "development": svc.estimated_team_size,
                            "qa": 2,
                        },
                        success_criteria=[
                            f"{svc.name} deployed and operational",
                            "API contracts validated",
                            "Data migration complete",
                            "Traffic cutover successful",
                        ],
                        rollback_strategy="Feature flag to route to legacy service",
                    )
                )

        # Final phase: Decommissioning
        roadmap.phases.append(
            MigrationPhase(
                name="Legacy Decommissioning",
                description="Decommission legacy systems",
                order=len(roadmap.phases),
                estimated_duration_weeks=4,
                team_requirements={"operations": 2, "development": 2},
                success_criteria=[
                    "All traffic on new systems",
                    "Legacy systems powered down",
                    "Data archived",
                    "Cost savings realized",
                ],
            )
        )

        # Calculate totals
        roadmap.total_duration_weeks = sum(
            p.estimated_duration_weeks for p in roadmap.phases
        )

        return roadmap

    def _estimate_cost_reduction(
        self, current: CurrentArchitecture, target_cloud: CloudProvider
    ) -> float:
        """Estimate potential cost reduction."""
        # Base estimate on common scenarios
        base_reduction = 20.0

        # Additional savings for serverless
        if current.peak_transactions_per_second < 100:
            base_reduction += 15.0  # Good serverless candidate

        # Managed services savings
        base_reduction += len(current.data_stores) * 5.0

        # Cap at reasonable maximum
        return min(base_reduction, 50.0)

    def _estimate_performance_improvement(
        self, current: CurrentArchitecture, strategy: ModernizationStrategy
    ) -> float:
        """Estimate performance improvement potential."""
        base_improvement = 30.0

        if strategy == ModernizationStrategy.REFACTOR:
            base_improvement += 20.0  # Microservices allow targeted scaling

        if current.style == ArchitectureStyle.MONOLITH:
            base_improvement += 15.0  # Breaking up monolith typically helps

        return min(base_improvement, 80.0)

    def _determine_target_style(
        self, current: CurrentArchitecture, strategy: ModernizationStrategy
    ) -> ArchitectureStyle:
        """Determine target architecture style."""
        if strategy == ModernizationStrategy.REFACTOR:
            if current.peak_transactions_per_second > 10000:
                return ArchitectureStyle.EVENT_DRIVEN
            return ArchitectureStyle.MICROSERVICES
        elif strategy == ModernizationStrategy.REPLATFORM:
            return ArchitectureStyle.MODULAR_MONOLITH
        elif strategy == ModernizationStrategy.REHOST:
            return current.style

        return ArchitectureStyle.MICROSERVICES

    def _build_business_case(
        self,
        current: CurrentArchitecture,
        target: TargetArchitecture,
        roadmap: MigrationRoadmap | None,
    ) -> dict[str, Any]:
        """Build business case for modernization."""
        return {
            "executive_summary": f"Modernize {current.name} from {current.style.value} to {target.style.value}",
            "key_benefits": [
                f"Estimated {target.estimated_cost_reduction_percent:.0f}% cost reduction",
                f"Estimated {target.estimated_performance_improvement_percent:.0f}% performance improvement",
                "Improved scalability and reliability",
                "Faster time-to-market for new features",
                "Reduced technical debt",
            ],
            "estimated_timeline_weeks": roadmap.total_duration_weeks if roadmap else 24,
            "estimated_investment": f"${roadmap.total_duration_weeks * 50000 if roadmap else 1200000}",
            "roi_timeline_months": 18,
            "risk_summary": f"{len(target.risks)} identified risks with mitigation strategies",
            "recommended_approach": target.cloud_provider.value.upper(),
            "success_metrics": [
                "Response time < 200ms p99",
                "Availability > 99.9%",
                "Deployment frequency > 10/week",
                "Lead time < 1 day",
            ],
        }

    async def get_pattern_recommendations(
        self, requirements: list[str]
    ) -> list[ArchitecturePattern]:
        """Get pattern recommendations based on requirements."""
        recommendations = []

        requirement_pattern_map = {
            "high_availability": ["circuit_breaker", "saga"],
            "scalability": ["cqrs", "event_sourcing"],
            "legacy_migration": ["strangler_fig", "anti_corruption_layer"],
            "microservices": ["api_gateway", "sidecar", "backends_for_frontends"],
            "event_driven": ["event_sourcing", "saga", "cqrs"],
            "distributed_transactions": ["saga"],
        }

        for req in requirements:
            req_lower = req.lower().replace(" ", "_")
            patterns = requirement_pattern_map.get(req_lower, [])
            for pattern_name in patterns:
                if pattern_name in self._architecture_patterns:
                    pattern = self._architecture_patterns[pattern_name]
                    if pattern not in recommendations:
                        recommendations.append(pattern)

        return recommendations

    async def get_technology_modernization_options(
        self, current_technology: str
    ) -> dict[str, Any]:
        """Get modernization options for a specific technology."""
        return self._technology_modernization_map.get(
            current_technology,
            {
                "alternatives": [],
                "rationale": "No specific recommendation available",
                "migration_complexity": "unknown",
            },
        )
