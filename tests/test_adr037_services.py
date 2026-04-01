"""Tests for ADR-037 AWS Agent Capability Replication Services

Comprehensive tests for all new services implementing ADR-037:
- OAuth Delegation Service
- Browser Tool Agent
- Code Interpreter Agent
- Semantic Tool Search
- Deployment History Correlator
- Proactive Recommendation Engine
"""

from datetime import datetime, timedelta, timezone
from typing import Optional

import pytest

# ============================================================================
# Mock Protocols
# ============================================================================


class MockSecretsManager:
    """Mock Secrets Manager client."""

    def __init__(self):
        self.secrets = {"secret-arn": "test-secret-value"}

    async def get_secret(self, secret_id: str) -> str:
        return self.secrets.get(secret_id, "")

    async def put_secret(self, secret_id: str, value: str) -> None:
        self.secrets[secret_id] = value

    async def delete_secret(self, secret_id: str) -> bool:
        return self.secrets.pop(secret_id, None) is not None


class MockDynamoDB:
    """Mock DynamoDB client."""

    def __init__(self):
        self.tables: dict[str, list[dict]] = {}

    async def put_item(self, table_name: str, item: dict) -> None:
        if table_name not in self.tables:
            self.tables[table_name] = []
        self.tables[table_name].append(item)

    async def get_item(self, table_name: str, key: dict) -> Optional[dict]:
        items = self.tables.get(table_name, [])
        for item in items:
            match = all(item.get(k) == v for k, v in key.items())
            if match:
                return item
        return None

    async def delete_item(self, table_name: str, key: dict) -> None:
        if table_name in self.tables:
            self.tables[table_name] = [
                item
                for item in self.tables[table_name]
                if not all(item.get(k) == v for k, v in key.items())
            ]

    async def query(
        self, table_name: str, key_condition: str, values: dict, **kwargs
    ) -> list[dict]:
        return self.tables.get(table_name, [])


class MockHTTPClient:
    """Mock HTTP client."""

    async def post(self, url: str, data: dict, headers: Optional[dict] = None) -> dict:
        return {
            "access_token": "test-access-token",
            "refresh_token": "test-refresh-token",
            "token_type": "Bearer",
            "expires_in": 3600,
        }


class MockEncryption:
    """Mock encryption service."""

    def encrypt(self, plaintext: str) -> str:
        return f"encrypted:{plaintext}"

    def decrypt(self, ciphertext: str) -> str:
        return ciphertext.replace("encrypted:", "")


class MockEmbeddingService:
    """Mock embedding service."""

    async def embed_text(self, text: str) -> list[float]:
        # Simple hash-based embedding for testing
        return [float(ord(c) % 10) / 10 for c in text[:10].ljust(10)]

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        return [await self.embed_text(t) for t in texts]


# ============================================================================
# OAuth Delegation Service Tests
# ============================================================================


class TestOAuthDelegationService:
    """Tests for OAuth Delegation Service."""

    @pytest.fixture
    def service(self):
        from src.services.oauth_delegation_service import (
            OAuthDelegationConfig,
            OAuthDelegationService,
        )

        return OAuthDelegationService(
            secrets_client=MockSecretsManager(),
            dynamodb_client=MockDynamoDB(),
            http_client=MockHTTPClient(),
            encryption_service=MockEncryption(),
            config=OAuthDelegationConfig(),
        )

    @pytest.fixture
    def provider(self):
        from src.services.oauth_delegation_service import (
            OAuthProvider,
            OAuthProviderType,
        )

        return OAuthProvider(
            provider_id="test-provider",
            provider_type=OAuthProviderType.CUSTOM,
            client_id="test-client-id",
            client_secret_arn="secret-arn",
            authorization_url="https://auth.example.com/authorize",
            token_url="https://auth.example.com/token",
            scopes=["read", "write"],
        )

    @pytest.mark.asyncio
    async def test_register_provider(self, service, provider):
        """Test provider registration."""
        await service.register_provider(provider)

        retrieved = await service.get_provider("test-provider")
        assert retrieved is not None
        assert retrieved.provider_id == "test-provider"
        assert retrieved.client_id == "test-client-id"

    @pytest.mark.asyncio
    async def test_initiate_authorization(self, service, provider):
        """Test authorization flow initiation."""
        await service.register_provider(provider)

        request = await service.initiate_authorization(
            agent_id="test-agent",
            user_id="test-user",
            provider_id="test-provider",
            scopes=["read"],
            redirect_uri="https://app.example.com/callback",
        )

        assert request.agent_id == "test-agent"
        assert request.user_id == "test-user"
        assert request.state is not None
        assert "code_challenge" in request.authorization_url

    @pytest.mark.asyncio
    async def test_get_service_stats(self, service, provider):
        """Test service statistics."""
        await service.register_provider(provider)

        stats = service.get_service_stats()
        assert stats["providers_cached"] == 1

    def test_generate_code_challenge(self, service):
        """Test PKCE code challenge generation."""
        verifier = "test-code-verifier-12345678901234567890"
        challenge = service._generate_code_challenge(verifier)

        assert challenge is not None
        assert len(challenge) > 0
        assert "=" not in challenge  # Base64url encoded


class TestDelegatedToken:
    """Tests for DelegatedToken dataclass."""

    def test_is_expired(self):
        from src.services.oauth_delegation_service import DelegatedToken

        token = DelegatedToken(
            token_id="test-token",
            agent_id="agent",
            user_id="user",
            provider_id="provider",
            access_token_encrypted="encrypted",
            refresh_token_encrypted="encrypted",
            id_token_encrypted=None,
            token_type="Bearer",
            scopes=["read"],
            expires_at=datetime.now(timezone.utc) - timedelta(hours=1),
            refresh_expires_at=None,
            user_info=None,
        )

        assert token.is_expired() is True

    def test_is_not_expired(self):
        from src.services.oauth_delegation_service import DelegatedToken

        token = DelegatedToken(
            token_id="test-token",
            agent_id="agent",
            user_id="user",
            provider_id="provider",
            access_token_encrypted="encrypted",
            refresh_token_encrypted="encrypted",
            id_token_encrypted=None,
            token_type="Bearer",
            scopes=["read"],
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
            refresh_expires_at=None,
            user_info=None,
        )

        assert token.is_expired() is False

    def test_can_refresh(self):
        from src.services.oauth_delegation_service import DelegatedToken

        token = DelegatedToken(
            token_id="test-token",
            agent_id="agent",
            user_id="user",
            provider_id="provider",
            access_token_encrypted="encrypted",
            refresh_token_encrypted="encrypted",
            id_token_encrypted=None,
            token_type="Bearer",
            scopes=["read"],
            expires_at=datetime.now(timezone.utc),
            refresh_expires_at=None,
            user_info=None,
        )

        assert token.can_refresh() is True


# ============================================================================
# Browser Tool Agent Tests
# ============================================================================


class TestBrowserToolAgent:
    """Tests for Browser Tool Agent."""

    @pytest.fixture
    def agent(self):
        from src.agents.browser_tool_agent import BrowserToolAgent

        return BrowserToolAgent()

    @pytest.mark.asyncio
    async def test_create_session(self, agent):
        """Test browser session creation."""
        session_id = await agent.create_session()

        assert session_id is not None
        assert len(session_id) > 0

    @pytest.mark.asyncio
    async def test_execute_navigate_action(self, agent):
        """Test navigation action."""
        from src.agents.browser_tool_agent import BrowserAction

        session_id = await agent.create_session()

        action = BrowserAction.navigate("https://example.com")
        state = await agent.execute_action(session_id, action)

        assert state.session_id == session_id

    @pytest.mark.asyncio
    async def test_execute_click_action(self, agent):
        """Test click action."""
        from src.agents.browser_tool_agent import BrowserAction

        session_id = await agent.create_session()

        action = BrowserAction.click("#button")
        state = await agent.execute_action(session_id, action)

        assert state is not None

    @pytest.mark.asyncio
    async def test_execute_workflow(self, agent):
        """Test workflow execution."""
        from src.agents.browser_tool_agent import BrowserAction

        session_id = await agent.create_session()

        actions = [
            BrowserAction.navigate("https://example.com"),
            BrowserAction.wait_for("#content"),
            BrowserAction.click("#button"),
        ]

        states = await agent.execute_workflow(session_id, actions)
        assert len(states) == 3

    @pytest.mark.asyncio
    async def test_new_tab(self, agent):
        """Test creating new tab."""
        session_id = await agent.create_session()

        tab_id = await agent.new_tab(session_id, "https://example.com")

        assert tab_id is not None

    @pytest.mark.asyncio
    async def test_close_session(self, agent):
        """Test session closure."""
        session_id = await agent.create_session()

        await agent.close_session(session_id)

        with pytest.raises(ValueError):
            from src.agents.browser_tool_agent import BrowserAction

            await agent.execute_action(
                session_id, BrowserAction.navigate("https://example.com")
            )

    def test_get_service_stats(self, agent):
        """Test service statistics."""
        stats = agent.get_service_stats()

        assert "active_sessions" in stats
        assert "total_actions_executed" in stats


class TestBrowserAction:
    """Tests for BrowserAction dataclass."""

    def test_navigate_action(self):
        from src.agents.browser_tool_agent import BrowserAction, BrowserActionType

        action = BrowserAction.navigate("https://example.com")

        assert action.action_type == BrowserActionType.NAVIGATE
        assert action.value == "https://example.com"

    def test_click_action(self):
        from src.agents.browser_tool_agent import BrowserAction, BrowserActionType

        action = BrowserAction.click("#button")

        assert action.action_type == BrowserActionType.CLICK
        assert action.selector == "#button"

    def test_type_action(self):
        from src.agents.browser_tool_agent import BrowserAction, BrowserActionType

        action = BrowserAction.type_text("#input", "hello")

        assert action.action_type == BrowserActionType.TYPE
        assert action.value == "hello"


# ============================================================================
# Code Interpreter Agent Tests
# ============================================================================


class TestCodeInterpreterAgent:
    """Tests for Code Interpreter Agent."""

    @pytest.fixture
    def agent(self):
        from src.agents.code_interpreter_agent import CodeInterpreterAgent

        return CodeInterpreterAgent()

    @pytest.mark.asyncio
    async def test_execute_python(self, agent):
        """Test Python code execution."""
        from src.agents.code_interpreter_agent import (
            CodeExecutionRequest,
            ExecutionStatus,
            SupportedLanguage,
        )

        request = CodeExecutionRequest(
            code="print('Hello, World!')",
            language=SupportedLanguage.PYTHON,
        )

        result = await agent.execute(request)

        assert result.status == ExecutionStatus.SUCCESS
        assert result.exit_code == 0

    @pytest.mark.asyncio
    async def test_validate_empty_code(self, agent):
        """Test validation of empty code."""
        from src.agents.code_interpreter_agent import (
            CodeExecutionRequest,
            ExecutionStatus,
            SupportedLanguage,
        )

        request = CodeExecutionRequest(
            code="",
            language=SupportedLanguage.PYTHON,
        )

        result = await agent.execute(request)

        assert result.status == ExecutionStatus.ERROR
        assert "Empty code" in result.error_message

    @pytest.mark.asyncio
    async def test_kill_execution(self, agent):
        """Test execution termination."""
        result = await agent.kill_execution("nonexistent")
        assert result is False

    def test_get_supported_languages(self, agent):
        """Test language listing."""
        languages = agent.get_supported_languages()

        assert len(languages) > 0
        assert any(lang["language"] == "python" for lang in languages)

    def test_get_service_stats(self, agent):
        """Test service statistics."""
        stats = agent.get_service_stats()

        assert "active_sandboxes" in stats
        assert "allowed_languages" in stats


class TestCodeExecutionRequest:
    """Tests for CodeExecutionRequest dataclass."""

    def test_default_values(self):
        from src.agents.code_interpreter_agent import (
            CodeExecutionRequest,
            SupportedLanguage,
        )

        request = CodeExecutionRequest(
            code="print('test')",
            language=SupportedLanguage.PYTHON,
        )

        assert request.timeout_seconds == 60
        assert request.memory_mb == 256
        assert request.working_directory == "/workspace"


# ============================================================================
# Semantic Tool Search Tests
# ============================================================================


class TestSemanticToolSearch:
    """Tests for Semantic Tool Search."""

    @pytest.fixture
    def search(self):
        from src.services.semantic_tool_search import SemanticToolSearch

        return SemanticToolSearch(
            embedding_service=MockEmbeddingService(),
        )

    @pytest.fixture
    def sample_tool(self):
        from src.services.semantic_tool_search import ToolCategory, ToolDefinition

        return ToolDefinition(
            tool_id="file_read",
            name="Read File",
            description="Read contents of a file from the filesystem",
            category=ToolCategory.FILE_OPERATIONS,
            tags=["file", "read", "filesystem"],
        )

    @pytest.mark.asyncio
    async def test_index_tool(self, search, sample_tool):
        """Test tool indexing."""
        await search.index_tool(sample_tool)

        tool = search.get_tool("file_read")
        assert tool is not None
        assert tool.name == "Read File"

    @pytest.mark.asyncio
    async def test_search_tools(self, search, sample_tool):
        """Test tool search."""
        await search.index_tool(sample_tool)

        results = await search.search_tools("read a file")

        assert len(results) > 0
        assert results[0].tool.tool_id == "file_read"

    @pytest.mark.asyncio
    async def test_recommend_tools(self, search, sample_tool):
        """Test tool recommendations."""
        await search.index_tool(sample_tool)

        recommendations = await search.recommend_tools(
            task_description="I need to read configuration files"
        )

        assert len(recommendations) > 0

    @pytest.mark.asyncio
    async def test_find_similar_tools(self, search, sample_tool):
        """Test finding similar tools."""
        from src.services.semantic_tool_search import ToolCategory, ToolDefinition

        await search.index_tool(sample_tool)
        await search.index_tool(
            ToolDefinition(
                tool_id="file_write",
                name="Write File",
                description="Write contents to a file",
                category=ToolCategory.FILE_OPERATIONS,
            )
        )

        similar = await search.find_similar_tools("file_read")
        assert len(similar) > 0

    def test_record_tool_usage(self, search, sample_tool):
        """Test usage recording."""
        search._tools[sample_tool.tool_id] = sample_tool

        search.record_tool_usage(sample_tool.tool_id, success=True)

        assert sample_tool.usage_count == 1

    def test_list_tools(self, search, sample_tool):
        """Test tool listing."""
        search._tools[sample_tool.tool_id] = sample_tool

        tools = search.list_tools()
        assert len(tools) == 1

    def test_get_categories(self, search, sample_tool):
        """Test category listing."""
        search._tools[sample_tool.tool_id] = sample_tool

        categories = search.get_categories()
        assert len(categories) > 0


class TestToolDefinition:
    """Tests for ToolDefinition dataclass."""

    def test_default_values(self):
        from src.services.semantic_tool_search import (
            ToolCategory,
            ToolComplexity,
            ToolDefinition,
        )

        tool = ToolDefinition(
            tool_id="test",
            name="Test Tool",
            description="A test tool",
        )

        assert tool.category == ToolCategory.SYSTEM
        assert tool.complexity == ToolComplexity.SIMPLE
        assert tool.deprecated is False


# ============================================================================
# Deployment History Correlator Tests
# ============================================================================


class TestDeploymentHistoryCorrelator:
    """Tests for Deployment History Correlator."""

    @pytest.fixture
    def correlator(self):
        from src.services.deployment_history_correlator import (
            DeploymentHistoryCorrelator,
        )

        return DeploymentHistoryCorrelator(
            dynamodb_client=MockDynamoDB(),
        )

    @pytest.fixture
    def sample_event(self):
        from src.services.deployment_history_correlator import (
            DeploymentEvent,
            DeploymentEventType,
        )

        return DeploymentEvent(
            event_id="deploy-001",
            event_type=DeploymentEventType.DEPLOY,
            service="api-service",
            environment="production",
            timestamp=datetime.now(timezone.utc) - timedelta(minutes=30),
            git_commit="abc123",
            changed_files=["src/api.py", "config/settings.yaml"],
            deployer="deploy-bot",
        )

    @pytest.mark.asyncio
    async def test_ingest_deployment(self, correlator, sample_event):
        """Test deployment ingestion."""
        await correlator.ingest_deployment(sample_event)

        assert len(correlator._events_cache) == 1

    @pytest.mark.asyncio
    async def test_correlate_incident(self, correlator, sample_event):
        """Test incident correlation."""
        await correlator.ingest_deployment(sample_event)

        correlations = await correlator.correlate_incident(
            incident_time=datetime.now(timezone.utc),
            affected_services=["api-service"],
        )

        assert len(correlations) > 0
        assert correlations[0].deployment.event_id == "deploy-001"

    @pytest.mark.asyncio
    async def test_analyze_blast_radius(self, correlator, sample_event):
        """Test blast radius analysis."""
        analysis = await correlator.analyze_blast_radius(sample_event)

        assert analysis.deployment_id == "deploy-001"
        assert "api-service" in analysis.affected_services
        assert analysis.risk_score >= 0
        assert analysis.risk_score <= 1

    def test_register_service_dependency(self, correlator):
        """Test dependency registration."""
        correlator.register_service_dependency(
            "web-service", ["api-service", "database"]
        )

        assert "web-service" in correlator._service_dependencies

    def test_get_service_stats(self, correlator):
        """Test service statistics."""
        stats = correlator.get_service_stats()

        assert "cached_events" in stats
        assert "registered_dependencies" in stats


class TestDeploymentEvent:
    """Tests for DeploymentEvent dataclass."""

    def test_affects_service_direct(self):
        from src.services.deployment_history_correlator import (
            DeploymentEvent,
            DeploymentEventType,
        )

        event = DeploymentEvent(
            event_id="test",
            event_type=DeploymentEventType.DEPLOY,
            service="api",
            environment="prod",
            timestamp=datetime.now(timezone.utc),
        )

        assert event.affects_service("api") is True
        assert event.affects_service("other") is False


# ============================================================================
# Proactive Recommendation Engine Tests
# ============================================================================


class TestProactiveRecommendationEngine:
    """Tests for Proactive Recommendation Engine."""

    @pytest.fixture
    def engine(self):
        from src.services.proactive_recommendation_engine import (
            ProactiveRecommendationEngine,
        )

        return ProactiveRecommendationEngine()

    @pytest.mark.asyncio
    async def test_analyze_observability(self, engine):
        """Test observability analysis."""
        from src.services.proactive_recommendation_engine import ObservabilityConfig

        config = ObservabilityConfig(
            log_retention_days=7,
            tracing_enabled=False,
            alarm_count=0,
        )

        recommendations = await engine.analyze_observability(config)

        assert len(recommendations) > 0
        titles = [r.title for r in recommendations]
        assert "Increase log retention period" in titles
        assert "Enable distributed tracing" in titles

    @pytest.mark.asyncio
    async def test_analyze_infrastructure(self, engine):
        """Test infrastructure analysis."""
        from src.services.proactive_recommendation_engine import CostData, ResourceGraph

        graph = ResourceGraph(
            nodes=[
                {"id": "server-1", "cpu_utilization": 10},
                {"id": "db-1", "incoming_edges": 5, "has_redundancy": False},
            ]
        )
        cost = CostData(monthly_total=10000, trend="increasing")

        recommendations = await engine.analyze_infrastructure(graph, cost)

        assert len(recommendations) > 0

    @pytest.mark.asyncio
    async def test_analyze_deployment_pipeline(self, engine):
        """Test pipeline analysis."""
        from src.services.proactive_recommendation_engine import PipelineConfig

        config = PipelineConfig(
            has_tests=False,
            has_security_scan=False,
            has_approval_gate=False,
        )

        recommendations = await engine.analyze_deployment_pipeline(config, [])

        assert len(recommendations) > 0
        priorities = [r.priority.value for r in recommendations]
        assert "critical" in priorities

    @pytest.mark.asyncio
    async def test_analyze_resilience(self, engine):
        """Test resilience analysis."""
        from src.services.proactive_recommendation_engine import ArchitectureSpec

        arch = ArchitectureSpec(
            services=["api", "worker"],
            has_circuit_breakers=False,
            has_rate_limiting=False,
            has_health_checks=False,
        )

        recommendations = await engine.analyze_resilience(arch, [])

        assert len(recommendations) > 0
        titles = [r.title for r in recommendations]
        assert "Implement circuit breakers" in titles
        assert "Implement rate limiting" in titles

    def test_get_recommendation_summary(self, engine):
        """Test recommendation summary."""
        summary = engine.get_recommendation_summary()

        assert summary.total_count == 0

    def test_get_service_stats(self, engine):
        """Test service statistics."""
        stats = engine.get_service_stats()

        assert "total_recommendations" in stats
        assert "by_category" in stats


class TestRecommendationPriority:
    """Tests for recommendation priority handling."""

    @pytest.mark.asyncio
    async def test_critical_recommendations(self):
        from src.services.proactive_recommendation_engine import (
            PipelineConfig,
            ProactiveRecommendationEngine,
            RecommendationPriority,
        )

        engine = ProactiveRecommendationEngine()

        config = PipelineConfig(has_security_scan=False)
        recommendations = await engine.analyze_deployment_pipeline(config, [])

        critical = [
            r for r in recommendations if r.priority == RecommendationPriority.CRITICAL
        ]

        assert len(critical) > 0


# ============================================================================
# Integration Tests
# ============================================================================


class TestADR037Integration:
    """Integration tests for ADR-037 services."""

    @pytest.mark.asyncio
    async def test_full_browser_workflow(self):
        """Test complete browser automation workflow."""
        from src.agents.browser_tool_agent import BrowserAction, BrowserToolAgent

        agent = BrowserToolAgent()
        session_id = await agent.create_session()

        # Execute workflow
        actions = [
            BrowserAction.navigate("https://example.com"),
            BrowserAction.wait_for("body", timeout_ms=5000),
            BrowserAction.screenshot(),
        ]

        states = await agent.execute_workflow(session_id, actions)
        assert len(states) == 3

        # Check history
        history = await agent.get_action_history(session_id)
        assert len(history) == 3

        # Cleanup
        await agent.close_session(session_id)

    @pytest.mark.asyncio
    async def test_full_search_workflow(self):
        """Test complete tool search workflow."""
        from src.services.semantic_tool_search import (
            SemanticToolSearch,
            ToolCategory,
            ToolDefinition,
        )

        search = SemanticToolSearch(embedding_service=MockEmbeddingService())

        # Index multiple tools
        tools = [
            ToolDefinition(
                tool_id="read_file",
                name="Read File",
                description="Read file contents",
                category=ToolCategory.FILE_OPERATIONS,
            ),
            ToolDefinition(
                tool_id="write_file",
                name="Write File",
                description="Write content to file",
                category=ToolCategory.FILE_OPERATIONS,
            ),
            ToolDefinition(
                tool_id="run_tests",
                name="Run Tests",
                description="Execute test suite",
                category=ToolCategory.TESTING,
            ),
        ]

        indexed = await search.index_tools_batch(tools)
        assert indexed == 3

        # Search
        results = await search.search_tools("file operations")
        assert len(results) > 0

        # Record usage
        search.record_tool_usage("read_file", success=True)

        # Get stats
        stats = search.get_service_stats()
        assert stats["indexed_tools"] == 3

    @pytest.mark.asyncio
    async def test_deployment_correlation_workflow(self):
        """Test complete deployment correlation workflow."""
        from src.services.deployment_history_correlator import (
            DeploymentEvent,
            DeploymentEventType,
            DeploymentHistoryCorrelator,
        )

        correlator = DeploymentHistoryCorrelator(dynamodb_client=MockDynamoDB())

        # Register dependencies
        correlator.register_service_dependency("frontend", ["api"])
        correlator.register_service_dependency("api", ["database"])

        # Ingest deployments
        now = datetime.now(timezone.utc)
        events = [
            DeploymentEvent(
                event_id="d1",
                event_type=DeploymentEventType.DEPLOY,
                service="api",
                environment="prod",
                timestamp=now - timedelta(minutes=30),
                changed_files=["src/main.py"],
            ),
            DeploymentEvent(
                event_id="d2",
                event_type=DeploymentEventType.CONFIG_CHANGE,
                service="database",
                environment="prod",
                timestamp=now - timedelta(minutes=15),
            ),
        ]

        for event in events:
            await correlator.ingest_deployment(event)

        # Correlate incident
        correlations = await correlator.correlate_incident(
            incident_time=now,
            affected_services=["api", "frontend"],
        )

        assert len(correlations) >= 1

    @pytest.mark.asyncio
    async def test_recommendation_workflow(self):
        """Test complete recommendation workflow."""
        from src.services.proactive_recommendation_engine import (
            ArchitectureSpec,
            ObservabilityConfig,
            PipelineConfig,
            ProactiveRecommendationEngine,
            ResourceGraph,
        )

        engine = ProactiveRecommendationEngine()

        # Analyze all areas
        await engine.analyze_observability(ObservabilityConfig())
        await engine.analyze_infrastructure(ResourceGraph())
        await engine.analyze_deployment_pipeline(PipelineConfig(), [])
        await engine.analyze_resilience(ArchitectureSpec(), [])

        # Get summary
        summary = engine.get_recommendation_summary()
        assert summary.total_count > 0

        # Filter by category
        from src.services.proactive_recommendation_engine import RecommendationCategory

        obs_recs = await engine.get_all_recommendations(
            category=RecommendationCategory.OBSERVABILITY
        )
        assert len(obs_recs) > 0
