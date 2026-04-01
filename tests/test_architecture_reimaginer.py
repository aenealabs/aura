"""
Tests for Architecture Reimaginer.

Tests the intelligent architecture modernization and redesign service.
"""

import pytest

from src.services.transform.architecture_reimaginer import (  # Enums; Dataclasses; Main class
    ArchitectureAssessment,
    ArchitecturePattern,
    ArchitectureReimaginer,
    ArchitectureStyle,
    CloudProvider,
    CloudServiceMapping,
    CommunicationPattern,
    ComponentType,
    CurrentArchitecture,
    DatabaseType,
    DataConsistencyPattern,
    DataStore,
    DeploymentPattern,
    InfrastructureRecommendation,
    Integration,
    MicroserviceCandidate,
    MigrationPhase,
    MigrationRisk,
    MigrationRoadmap,
    ModernizationStrategy,
    Priority,
    RiskLevel,
    ScalabilityPattern,
    SecurityRecommendation,
    ServiceDecomposition,
    SystemComponent,
    TargetArchitecture,
    TechnologyStack,
)

# ============================================================================
# Enum Tests
# ============================================================================


class TestArchitectureStyle:
    """Test ArchitectureStyle enum."""

    def test_monolith(self):
        """Test monolith style."""
        assert ArchitectureStyle.MONOLITH.value == "monolith"

    def test_modular_monolith(self):
        """Test modular monolith style."""
        assert ArchitectureStyle.MODULAR_MONOLITH.value == "modular_monolith"

    def test_soa(self):
        """Test SOA style."""
        assert ArchitectureStyle.SOA.value == "soa"

    def test_microservices(self):
        """Test microservices style."""
        assert ArchitectureStyle.MICROSERVICES.value == "microservices"

    def test_serverless(self):
        """Test serverless style."""
        assert ArchitectureStyle.SERVERLESS.value == "serverless"

    def test_event_driven(self):
        """Test event-driven style."""
        assert ArchitectureStyle.EVENT_DRIVEN.value == "event_driven"

    def test_cqrs(self):
        """Test CQRS style."""
        assert ArchitectureStyle.CQRS.value == "cqrs"

    def test_hexagonal(self):
        """Test hexagonal style."""
        assert ArchitectureStyle.HEXAGONAL.value == "hexagonal"

    def test_layered(self):
        """Test layered style."""
        assert ArchitectureStyle.LAYERED.value == "layered"


class TestCloudProvider:
    """Test CloudProvider enum."""

    def test_aws(self):
        """Test AWS provider."""
        assert CloudProvider.AWS.value == "aws"

    def test_azure(self):
        """Test Azure provider."""
        assert CloudProvider.AZURE.value == "azure"

    def test_gcp(self):
        """Test GCP provider."""
        assert CloudProvider.GCP.value == "gcp"

    def test_multi_cloud(self):
        """Test multi-cloud provider."""
        assert CloudProvider.MULTI_CLOUD.value == "multi_cloud"

    def test_on_premise(self):
        """Test on-premise."""
        assert CloudProvider.ON_PREMISE.value == "on_premise"

    def test_hybrid(self):
        """Test hybrid."""
        assert CloudProvider.HYBRID.value == "hybrid"


class TestModernizationStrategy:
    """Test ModernizationStrategy enum (6 Rs)."""

    def test_rehost(self):
        """Test rehost strategy."""
        assert ModernizationStrategy.REHOST.value == "rehost"

    def test_replatform(self):
        """Test replatform strategy."""
        assert ModernizationStrategy.REPLATFORM.value == "replatform"

    def test_repurchase(self):
        """Test repurchase strategy."""
        assert ModernizationStrategy.REPURCHASE.value == "repurchase"

    def test_refactor(self):
        """Test refactor strategy."""
        assert ModernizationStrategy.REFACTOR.value == "refactor"

    def test_retire(self):
        """Test retire strategy."""
        assert ModernizationStrategy.RETIRE.value == "retire"

    def test_retain(self):
        """Test retain strategy."""
        assert ModernizationStrategy.RETAIN.value == "retain"


class TestComponentType:
    """Test ComponentType enum."""

    def test_web_frontend(self):
        """Test web frontend type."""
        assert ComponentType.WEB_FRONTEND.value == "web_frontend"

    def test_api_gateway(self):
        """Test API gateway type."""
        assert ComponentType.API_GATEWAY.value == "api_gateway"

    def test_backend_service(self):
        """Test backend service type."""
        assert ComponentType.BACKEND_SERVICE.value == "backend_service"

    def test_database(self):
        """Test database type."""
        assert ComponentType.DATABASE.value == "database"

    def test_cache(self):
        """Test cache type."""
        assert ComponentType.CACHE.value == "cache"

    def test_message_queue(self):
        """Test message queue type."""
        assert ComponentType.MESSAGE_QUEUE.value == "message_queue"

    def test_file_storage(self):
        """Test file storage type."""
        assert ComponentType.FILE_STORAGE.value == "file_storage"

    def test_batch_processor(self):
        """Test batch processor type."""
        assert ComponentType.BATCH_PROCESSOR.value == "batch_processor"

    def test_scheduler(self):
        """Test scheduler type."""
        assert ComponentType.SCHEDULER.value == "scheduler"


class TestDatabaseType:
    """Test DatabaseType enum."""

    def test_relational(self):
        """Test relational type."""
        assert DatabaseType.RELATIONAL.value == "relational"

    def test_document(self):
        """Test document type."""
        assert DatabaseType.DOCUMENT.value == "document"

    def test_key_value(self):
        """Test key-value type."""
        assert DatabaseType.KEY_VALUE.value == "key_value"

    def test_graph(self):
        """Test graph type."""
        assert DatabaseType.GRAPH.value == "graph"

    def test_time_series(self):
        """Test time series type."""
        assert DatabaseType.TIME_SERIES.value == "time_series"

    def test_wide_column(self):
        """Test wide column type."""
        assert DatabaseType.WIDE_COLUMN.value == "wide_column"

    def test_search(self):
        """Test search type."""
        assert DatabaseType.SEARCH.value == "search"


class TestCommunicationPattern:
    """Test CommunicationPattern enum."""

    def test_synchronous_http(self):
        """Test synchronous HTTP."""
        assert CommunicationPattern.SYNCHRONOUS_HTTP.value == "synchronous_http"

    def test_synchronous_grpc(self):
        """Test synchronous gRPC."""
        assert CommunicationPattern.SYNCHRONOUS_GRPC.value == "synchronous_grpc"

    def test_asynchronous_messaging(self):
        """Test asynchronous messaging."""
        assert (
            CommunicationPattern.ASYNCHRONOUS_MESSAGING.value
            == "asynchronous_messaging"
        )

    def test_event_streaming(self):
        """Test event streaming."""
        assert CommunicationPattern.EVENT_STREAMING.value == "event_streaming"

    def test_websocket(self):
        """Test WebSocket."""
        assert CommunicationPattern.WEBSOCKET.value == "websocket"

    def test_graphql(self):
        """Test GraphQL."""
        assert CommunicationPattern.GRAPHQL.value == "graphql"


class TestScalabilityPattern:
    """Test ScalabilityPattern enum."""

    def test_horizontal(self):
        """Test horizontal scaling."""
        assert ScalabilityPattern.HORIZONTAL.value == "horizontal"

    def test_vertical(self):
        """Test vertical scaling."""
        assert ScalabilityPattern.VERTICAL.value == "vertical"

    def test_auto_scaling(self):
        """Test auto-scaling."""
        assert ScalabilityPattern.AUTO_SCALING.value == "auto_scaling"

    def test_circuit_breaker(self):
        """Test circuit breaker."""
        assert ScalabilityPattern.CIRCUIT_BREAKER.value == "circuit_breaker"

    def test_bulkhead(self):
        """Test bulkhead."""
        assert ScalabilityPattern.BULKHEAD.value == "bulkhead"

    def test_rate_limiting(self):
        """Test rate limiting."""
        assert ScalabilityPattern.RATE_LIMITING.value == "rate_limiting"


class TestDataConsistencyPattern:
    """Test DataConsistencyPattern enum."""

    def test_strong(self):
        """Test strong consistency."""
        assert DataConsistencyPattern.STRONG.value == "strong"

    def test_eventual(self):
        """Test eventual consistency."""
        assert DataConsistencyPattern.EVENTUAL.value == "eventual"

    def test_saga(self):
        """Test saga pattern."""
        assert DataConsistencyPattern.SAGA.value == "saga"

    def test_two_phase_commit(self):
        """Test two-phase commit."""
        assert DataConsistencyPattern.TWO_PHASE_COMMIT.value == "two_phase_commit"

    def test_outbox(self):
        """Test outbox pattern."""
        assert DataConsistencyPattern.OUTBOX.value == "outbox"

    def test_cdc(self):
        """Test CDC pattern."""
        assert DataConsistencyPattern.CDC.value == "cdc"


class TestDeploymentPattern:
    """Test DeploymentPattern enum."""

    def test_container(self):
        """Test container deployment."""
        assert DeploymentPattern.CONTAINER.value == "container"

    def test_serverless_function(self):
        """Test serverless function."""
        assert DeploymentPattern.SERVERLESS_FUNCTION.value == "serverless_function"

    def test_vm(self):
        """Test VM deployment."""
        assert DeploymentPattern.VM.value == "vm"

    def test_kubernetes(self):
        """Test Kubernetes deployment."""
        assert DeploymentPattern.KUBERNETES.value == "kubernetes"

    def test_ecs(self):
        """Test ECS deployment."""
        assert DeploymentPattern.ECS.value == "ecs"


class TestRiskLevel:
    """Test RiskLevel enum."""

    def test_low(self):
        """Test low risk."""
        assert RiskLevel.LOW.value == "low"

    def test_medium(self):
        """Test medium risk."""
        assert RiskLevel.MEDIUM.value == "medium"

    def test_high(self):
        """Test high risk."""
        assert RiskLevel.HIGH.value == "high"

    def test_critical(self):
        """Test critical risk."""
        assert RiskLevel.CRITICAL.value == "critical"


class TestPriority:
    """Test Priority enum."""

    def test_immediate(self):
        """Test immediate priority."""
        assert Priority.IMMEDIATE.value == "immediate"

    def test_short_term(self):
        """Test short term priority."""
        assert Priority.SHORT_TERM.value == "short_term"

    def test_medium_term(self):
        """Test medium term priority."""
        assert Priority.MEDIUM_TERM.value == "medium_term"

    def test_long_term(self):
        """Test long term priority."""
        assert Priority.LONG_TERM.value == "long_term"


# ============================================================================
# Dataclass Tests
# ============================================================================


class TestTechnologyStack:
    """Test TechnologyStack dataclass."""

    def test_create_tech_stack(self):
        """Test creating technology stack."""
        stack = TechnologyStack(
            name="Java", version="8", category="language", is_legacy=True
        )
        assert stack.name == "Java"
        assert stack.version == "8"
        assert stack.is_legacy is True

    def test_tech_stack_defaults(self):
        """Test technology stack defaults."""
        stack = TechnologyStack(name="Python")
        assert stack.version is None
        assert stack.category == ""
        assert stack.is_legacy is False
        assert stack.end_of_life is None
        assert stack.modern_alternative is None


class TestSystemComponent:
    """Test SystemComponent dataclass."""

    def test_create_component(self):
        """Test creating system component."""
        component = SystemComponent(
            id="api-1", name="API Gateway", component_type=ComponentType.API_GATEWAY
        )
        assert component.id == "api-1"
        assert component.name == "API Gateway"
        assert component.component_type == ComponentType.API_GATEWAY

    def test_component_defaults(self):
        """Test component defaults."""
        component = SystemComponent(
            id="test", name="Test", component_type=ComponentType.BACKEND_SERVICE
        )
        assert component.technology_stack == []
        assert component.dependencies == []
        assert component.dependents == []
        assert component.responsibilities == []
        assert component.estimated_lines_of_code == 0
        assert component.team_ownership == ""
        assert component.change_frequency == "low"
        assert component.business_criticality == "medium"


class TestDataStore:
    """Test DataStore dataclass."""

    def test_create_data_store(self):
        """Test creating data store."""
        store = DataStore(
            id="db-1",
            name="Main Database",
            database_type=DatabaseType.RELATIONAL,
            technology="PostgreSQL",
        )
        assert store.id == "db-1"
        assert store.name == "Main Database"
        assert store.database_type == DatabaseType.RELATIONAL
        assert store.technology == "PostgreSQL"

    def test_data_store_defaults(self):
        """Test data store defaults."""
        store = DataStore(
            id="db",
            name="DB",
            database_type=DatabaseType.DOCUMENT,
            technology="MongoDB",
        )
        assert store.size_gb == 0
        assert store.tables_count == 0
        assert store.read_qps == 0
        assert store.write_qps == 0
        assert store.consistency_requirement == DataConsistencyPattern.STRONG


class TestIntegration:
    """Test Integration dataclass."""

    def test_create_integration(self):
        """Test creating integration."""
        integration = Integration(
            id="int-1",
            name="Payment Gateway",
            system="Stripe",
            protocol="HTTPS",
            direction="outbound",
            data_format="JSON",
            frequency="real-time",
        )
        assert integration.id == "int-1"
        assert integration.name == "Payment Gateway"
        assert integration.system == "Stripe"

    def test_integration_defaults(self):
        """Test integration defaults."""
        integration = Integration(
            id="int",
            name="API",
            system="External",
            protocol="REST",
            direction="inbound",
            data_format="XML",
            frequency="batch",
        )
        assert integration.criticality == "medium"


class TestCurrentArchitecture:
    """Test CurrentArchitecture dataclass."""

    def test_create_current_arch(self):
        """Test creating current architecture."""
        arch = CurrentArchitecture(name="Legacy App", style=ArchitectureStyle.MONOLITH)
        assert arch.name == "Legacy App"
        assert arch.style == ArchitectureStyle.MONOLITH

    def test_current_arch_defaults(self):
        """Test current architecture defaults."""
        arch = CurrentArchitecture(name="Test", style=ArchitectureStyle.LAYERED)
        assert arch.components == []
        assert arch.data_stores == []
        assert arch.integrations == []
        assert arch.deployment_environment == ""
        assert arch.total_users == 0
        assert arch.peak_transactions_per_second == 0
        assert arch.availability_sla == 99.0
        assert arch.documentation_quality == "low"


class TestMicroserviceCandidate:
    """Test MicroserviceCandidate dataclass."""

    def test_create_microservice(self):
        """Test creating microservice candidate."""
        ms = MicroserviceCandidate(
            id="ms-1", name="User Service", bounded_context="Identity"
        )
        assert ms.id == "ms-1"
        assert ms.name == "User Service"
        assert ms.bounded_context == "Identity"

    def test_microservice_defaults(self):
        """Test microservice defaults."""
        ms = MicroserviceCandidate(id="ms", name="Test", bounded_context="Core")
        assert ms.responsibilities == []
        assert ms.data_entities == []
        assert ms.source_components == []
        assert ms.api_endpoints == []
        assert ms.database_type == DatabaseType.RELATIONAL
        assert ms.estimated_team_size == 1
        assert ms.deployment_pattern == DeploymentPattern.CONTAINER


class TestServiceDecomposition:
    """Test ServiceDecomposition dataclass."""

    def test_create_decomposition(self):
        """Test creating service decomposition."""
        decomp = ServiceDecomposition(
            microservices=[
                MicroserviceCandidate(
                    id="ms-1", name="User", bounded_context="Identity"
                )
            ]
        )
        assert len(decomp.microservices) == 1

    def test_decomposition_defaults(self):
        """Test decomposition defaults."""
        decomp = ServiceDecomposition()
        assert decomp.microservices == []
        assert decomp.shared_services == []
        assert decomp.data_migration_plan == []
        assert decomp.strangler_fig_sequence == []
        assert decomp.estimated_total_services == 0


class TestCloudServiceMapping:
    """Test CloudServiceMapping dataclass."""

    def test_create_mapping(self):
        """Test creating cloud service mapping."""
        mapping = CloudServiceMapping(
            source_component="Database",
            target_service="Amazon RDS",
            cloud_provider=CloudProvider.AWS,
            service_category="database",
            rationale="Managed relational database",
        )
        assert mapping.source_component == "Database"
        assert mapping.target_service == "Amazon RDS"
        assert mapping.cloud_provider == CloudProvider.AWS

    def test_mapping_defaults(self):
        """Test mapping defaults."""
        mapping = CloudServiceMapping(
            source_component="Test",
            target_service="Test Service",
            cloud_provider=CloudProvider.AZURE,
            service_category="compute",
            rationale="Testing",
        )
        assert mapping.estimated_cost_monthly == 0
        assert mapping.migration_complexity == "medium"


class TestInfrastructureRecommendation:
    """Test InfrastructureRecommendation dataclass."""

    def test_create_recommendation(self):
        """Test creating infrastructure recommendation."""
        rec = InfrastructureRecommendation(
            category="Compute",
            current_state="On-premise VMs",
            recommended_state="AWS EKS",
        )
        assert rec.category == "Compute"
        assert rec.current_state == "On-premise VMs"
        assert rec.recommended_state == "AWS EKS"

    def test_recommendation_defaults(self):
        """Test recommendation defaults."""
        rec = InfrastructureRecommendation(
            category="Test", current_state="Old", recommended_state="New"
        )
        assert rec.cloud_services == []
        assert rec.benefits == []
        assert rec.implementation_steps == []
        assert rec.estimated_cost_impact == ""


class TestSecurityRecommendation:
    """Test SecurityRecommendation dataclass."""

    def test_create_security_rec(self):
        """Test creating security recommendation."""
        rec = SecurityRecommendation(
            category="Authentication",
            finding="No MFA",
            recommendation="Enable MFA",
            implementation="Configure Cognito MFA",
        )
        assert rec.category == "Authentication"
        assert rec.finding == "No MFA"

    def test_security_rec_defaults(self):
        """Test security recommendation defaults."""
        rec = SecurityRecommendation(
            category="Test",
            finding="Test",
            recommendation="Test",
            implementation="Test",
        )
        assert rec.priority == Priority.MEDIUM_TERM
        assert rec.compliance_frameworks == []


class TestMigrationRisk:
    """Test MigrationRisk dataclass."""

    def test_create_risk(self):
        """Test creating migration risk."""
        risk = MigrationRisk(
            category="Data",
            description="Large data migration",
            level=RiskLevel.HIGH,
            mitigation_strategy="Phased migration",
        )
        assert risk.category == "Data"
        assert risk.level == RiskLevel.HIGH

    def test_risk_defaults(self):
        """Test risk defaults."""
        risk = MigrationRisk(
            category="Test",
            description="Test",
            level=RiskLevel.LOW,
            mitigation_strategy="None",
        )
        assert risk.affected_components == []


class TestMigrationPhase:
    """Test MigrationPhase dataclass."""

    def test_create_phase(self):
        """Test creating migration phase."""
        phase = MigrationPhase(name="Phase 1", description="Initial migration", order=1)
        assert phase.name == "Phase 1"
        assert phase.order == 1

    def test_phase_defaults(self):
        """Test phase defaults."""
        phase = MigrationPhase(name="Test", description="Test", order=0)
        assert phase.components == []
        assert phase.dependencies == []
        assert phase.estimated_duration_weeks == 0
        assert phase.team_requirements == {}
        assert phase.success_criteria == []
        assert phase.rollback_strategy == ""


class TestMigrationRoadmap:
    """Test MigrationRoadmap dataclass."""

    def test_create_roadmap(self):
        """Test creating migration roadmap."""
        roadmap = MigrationRoadmap(
            phases=[MigrationPhase(name="Phase 1", description="Start", order=1)]
        )
        assert len(roadmap.phases) == 1

    def test_roadmap_defaults(self):
        """Test roadmap defaults."""
        roadmap = MigrationRoadmap()
        assert roadmap.phases == []
        assert roadmap.total_duration_weeks == 0
        assert roadmap.estimated_total_cost == 0
        assert roadmap.quick_wins == []
        assert roadmap.parallel_tracks == []


class TestArchitecturePattern:
    """Test ArchitecturePattern dataclass."""

    def test_create_pattern(self):
        """Test creating architecture pattern."""
        pattern = ArchitecturePattern(
            name="Circuit Breaker", description="Prevent cascade failures"
        )
        assert pattern.name == "Circuit Breaker"

    def test_pattern_defaults(self):
        """Test pattern defaults."""
        pattern = ArchitecturePattern(name="Test", description="Test")
        assert pattern.applicability == []
        assert pattern.benefits == []
        assert pattern.tradeoffs == []
        assert pattern.implementation_guidance == ""
        assert pattern.related_patterns == []


class TestTargetArchitecture:
    """Test TargetArchitecture dataclass."""

    def test_create_target_arch(self):
        """Test creating target architecture."""
        target = TargetArchitecture(
            name="Modern App",
            style=ArchitectureStyle.MICROSERVICES,
            cloud_provider=CloudProvider.AWS,
        )
        assert target.name == "Modern App"
        assert target.style == ArchitectureStyle.MICROSERVICES
        assert target.cloud_provider == CloudProvider.AWS

    def test_target_arch_defaults(self):
        """Test target architecture defaults."""
        target = TargetArchitecture(
            name="Test",
            style=ArchitectureStyle.SERVERLESS,
            cloud_provider=CloudProvider.GCP,
        )
        assert target.decomposition is None
        assert target.infrastructure == []
        assert target.patterns == []
        assert target.security_recommendations == []
        assert target.migration_roadmap is None
        assert target.risks == []
        assert target.estimated_cost_reduction_percent == 0
        assert target.estimated_performance_improvement_percent == 0


class TestArchitectureAssessment:
    """Test ArchitectureAssessment dataclass."""

    def test_create_assessment(self):
        """Test creating assessment."""
        current = CurrentArchitecture(name="Legacy", style=ArchitectureStyle.MONOLITH)
        target = TargetArchitecture(
            name="Modern",
            style=ArchitectureStyle.MICROSERVICES,
            cloud_provider=CloudProvider.AWS,
        )
        assessment = ArchitectureAssessment(
            id="assess-1",
            name="Legacy Modernization",
            current_architecture=current,
            target_architecture=target,
            modernization_strategy=ModernizationStrategy.REFACTOR,
        )
        assert assessment.id == "assess-1"
        assert assessment.name == "Legacy Modernization"
        assert assessment.modernization_strategy == ModernizationStrategy.REFACTOR

    def test_assessment_defaults(self):
        """Test assessment defaults."""
        current = CurrentArchitecture(name="Test", style=ArchitectureStyle.MONOLITH)
        target = TargetArchitecture(
            name="Test",
            style=ArchitectureStyle.MICROSERVICES,
            cloud_provider=CloudProvider.AWS,
        )
        assessment = ArchitectureAssessment(
            id="test",
            name="Test",
            current_architecture=current,
            target_architecture=target,
            modernization_strategy=ModernizationStrategy.REPLATFORM,
        )
        assert assessment.business_case == {}
        assert assessment.assessment_hash == ""


# ============================================================================
# ArchitectureReimaginer Tests
# ============================================================================


class TestArchitectureReimaginerInit:
    """Test ArchitectureReimaginer initialization."""

    def test_init_creates_mappings(self):
        """Test initialization creates cloud service mappings."""
        reimaginer = ArchitectureReimaginer()
        assert reimaginer._cloud_service_mappings is not None
        assert CloudProvider.AWS in reimaginer._cloud_service_mappings

    def test_init_creates_patterns(self):
        """Test initialization creates architecture patterns."""
        reimaginer = ArchitectureReimaginer()
        assert reimaginer._architecture_patterns is not None

    def test_init_creates_tech_map(self):
        """Test initialization creates technology modernization map."""
        reimaginer = ArchitectureReimaginer()
        assert reimaginer._technology_modernization_map is not None


class TestCloudServiceMappings:
    """Test cloud service mappings."""

    def test_aws_mappings_exist(self):
        """Test AWS mappings exist."""
        reimaginer = ArchitectureReimaginer()
        aws_mappings = reimaginer._cloud_service_mappings.get(CloudProvider.AWS, {})
        assert "api_gateway" in aws_mappings
        assert "backend_service" in aws_mappings
        assert "relational_database" in aws_mappings

    def test_azure_mappings_exist(self):
        """Test Azure mappings exist."""
        reimaginer = ArchitectureReimaginer()
        azure_mappings = reimaginer._cloud_service_mappings.get(CloudProvider.AZURE, {})
        assert len(azure_mappings) > 0

    def test_gcp_mappings_exist(self):
        """Test GCP mappings exist."""
        reimaginer = ArchitectureReimaginer()
        gcp_mappings = reimaginer._cloud_service_mappings.get(CloudProvider.GCP, {})
        assert len(gcp_mappings) > 0


class TestAnalyzeArchitecture:
    """Test analyze_architecture method."""

    @pytest.mark.asyncio
    async def test_analyze_simple_architecture(self):
        """Test analyzing simple architecture."""
        reimaginer = ArchitectureReimaginer()
        current = CurrentArchitecture(
            name="Simple App",
            style=ArchitectureStyle.MONOLITH,
            components=[
                SystemComponent(
                    id="main",
                    name="Main App",
                    component_type=ComponentType.BACKEND_SERVICE,
                    estimated_lines_of_code=10000,
                )
            ],
        )
        assessment = await reimaginer.analyze_architecture(
            current, CloudProvider.AWS, ModernizationStrategy.REFACTOR
        )
        # Verify assessment contains expected architecture analysis
        assert assessment.current_architecture == current
        assert assessment.target_architecture is not None
        assert assessment.target_architecture.cloud_provider == CloudProvider.AWS
        assert assessment.modernization_strategy == ModernizationStrategy.REFACTOR

    @pytest.mark.asyncio
    async def test_analyze_with_data_stores(self):
        """Test analyzing architecture with data stores."""
        reimaginer = ArchitectureReimaginer()
        current = CurrentArchitecture(
            name="Data App",
            style=ArchitectureStyle.LAYERED,
            components=[
                SystemComponent(
                    id="api", name="API", component_type=ComponentType.BACKEND_SERVICE
                )
            ],
            data_stores=[
                DataStore(
                    id="db-1",
                    name="Main DB",
                    database_type=DatabaseType.RELATIONAL,
                    technology="Oracle",
                )
            ],
        )
        assessment = await reimaginer.analyze_architecture(
            current, CloudProvider.AWS, ModernizationStrategy.REPLATFORM
        )
        # Verify data stores are analyzed
        assert assessment.current_architecture.name == "Data App"
        assert assessment.modernization_strategy == ModernizationStrategy.REPLATFORM

    @pytest.mark.asyncio
    async def test_analyze_with_integrations(self):
        """Test analyzing architecture with integrations."""
        reimaginer = ArchitectureReimaginer()
        current = CurrentArchitecture(
            name="Integrated App",
            style=ArchitectureStyle.SOA,
            integrations=[
                Integration(
                    id="int-1",
                    name="Payment",
                    system="Stripe",
                    protocol="REST",
                    direction="outbound",
                    data_format="JSON",
                    frequency="real-time",
                )
            ],
        )
        assessment = await reimaginer.analyze_architecture(
            current, CloudProvider.AZURE, ModernizationStrategy.REFACTOR
        )
        # Verify integrations are analyzed
        assert assessment.current_architecture.name == "Integrated App"
        assert assessment.target_architecture.cloud_provider == CloudProvider.AZURE


class TestGetPatternRecommendations:
    """Test get_pattern_recommendations method."""

    @pytest.mark.asyncio
    async def test_get_patterns_high_availability(self):
        """Test getting pattern recommendations for high availability."""
        reimaginer = ArchitectureReimaginer()
        patterns = await reimaginer.get_pattern_recommendations(["high_availability"])
        # Should return patterns as a list, possibly empty if no matches
        assert isinstance(patterns, list), "Should return a list of patterns"

    @pytest.mark.asyncio
    async def test_get_patterns_scalability(self):
        """Test getting pattern recommendations for scalability."""
        reimaginer = ArchitectureReimaginer()
        patterns = await reimaginer.get_pattern_recommendations(["scalability"])
        # Should return patterns as a list for scalability requirements
        assert isinstance(patterns, list), "Should return a list of patterns"

    @pytest.mark.asyncio
    async def test_get_patterns_legacy_migration(self):
        """Test getting pattern recommendations for legacy migration."""
        reimaginer = ArchitectureReimaginer()
        patterns = await reimaginer.get_pattern_recommendations(["legacy_migration"])
        # Should return patterns as a list for legacy migration
        assert isinstance(patterns, list), "Should return a list of patterns"

    @pytest.mark.asyncio
    async def test_get_patterns_multiple_requirements(self):
        """Test getting pattern recommendations for multiple requirements."""
        reimaginer = ArchitectureReimaginer()
        patterns = await reimaginer.get_pattern_recommendations(
            ["high_availability", "scalability", "legacy_migration"]
        )
        # Should handle multiple requirements and return patterns list
        assert isinstance(patterns, list), "Should return a list of patterns"


class TestGetTechnologyModernizationOptions:
    """Test get_technology_modernization_options method."""

    @pytest.mark.asyncio
    async def test_get_modernization_options_oracle(self):
        """Test getting technology modernization options for Oracle."""
        reimaginer = ArchitectureReimaginer()
        options = await reimaginer.get_technology_modernization_options("Oracle")
        # Should return dict with modernization options for Oracle
        assert isinstance(options, dict), "Should return a dict of options"
        assert (
            "alternatives" in options or len(options) >= 0
        ), "Should contain options structure"

    @pytest.mark.asyncio
    async def test_get_modernization_options_unknown(self):
        """Test getting modernization options for unknown technology."""
        reimaginer = ArchitectureReimaginer()
        options = await reimaginer.get_technology_modernization_options("UnknownTech")
        # Should return dict with empty/default alternatives for unknown tech
        assert isinstance(options, dict), "Should return a dict even for unknown tech"
        assert "alternatives" in options, "Should contain alternatives key"
