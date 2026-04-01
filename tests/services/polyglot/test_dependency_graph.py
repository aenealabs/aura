"""
Tests for polyglot dependency graph service.
"""

import pytest

from src.services.polyglot import (
    CodeRelationship,
    DuplicateEntityError,
    EntityNotFoundError,
    GraphQuery,
    IndexStatus,
    Language,
    NeptuneShardRouter,
    PolyglotConfig,
    PolyglotDependencyGraph,
    RelationType,
    RepositoryNotIndexedError,
    get_dependency_graph,
    reset_dependency_graph,
)


class TestPolyglotConfig:
    """Tests for polyglot configuration."""

    def test_default_config(self):
        """Test default configuration values."""
        config = PolyglotConfig()
        assert config.enabled is True
        assert config.neptune.enabled is True
        assert config.sharding.num_shards == 8

    def test_for_testing(self):
        """Test test configuration."""
        config = PolyglotConfig.for_testing()
        assert config.environment == "test"
        assert config.neptune.enabled is False
        assert config.sharding.enabled is False

    def test_for_production(self):
        """Test production configuration."""
        config = PolyglotConfig.for_production()
        assert config.environment == "prod"
        assert config.sharding.num_shards == 8

    def test_validate_success(self):
        """Test validation with valid config."""
        config = PolyglotConfig()
        errors = config.validate()
        assert len(errors) == 0

    def test_validate_invalid_shards(self):
        """Test validation with invalid shard count."""
        config = PolyglotConfig()
        config.sharding.num_shards = 0
        errors = config.validate()
        assert any("num_shards" in e for e in errors)


class TestNeptuneShardRouter:
    """Tests for Neptune shard router."""

    def test_initialize(self, test_config):
        """Test router initialization."""
        router = NeptuneShardRouter(config=test_config)
        assert router.num_shards >= 1

    def test_get_shard_for_repository(self, test_config):
        """Test getting shard for repository."""
        router = NeptuneShardRouter(config=test_config)
        shard = router.get_shard_for_repository("repo-001")
        assert shard is not None
        assert isinstance(shard.shard_id, int)

    def test_consistent_shard_routing(self, test_config):
        """Test consistent shard routing."""
        router = NeptuneShardRouter(config=test_config)
        shard1 = router.get_shard_for_repository("repo-001")
        shard2 = router.get_shard_for_repository("repo-001")
        assert shard1.shard_id == shard2.shard_id

    def test_get_shards_for_query(self, test_config):
        """Test getting shards for query."""
        router = NeptuneShardRouter(config=test_config)
        shards = router.get_shards_for_query(["repo-001", "repo-002"])
        assert len(shards) >= 1

    def test_get_all_shards_for_global_query(self, test_config):
        """Test getting all shards for global query."""
        router = NeptuneShardRouter(config=test_config)
        shards = router.get_shards_for_query(None)
        assert len(shards) == router.num_shards

    def test_create_query_plan(self, test_config):
        """Test creating query plan."""
        router = NeptuneShardRouter(config=test_config)
        query = GraphQuery(
            query_id="q-001",
            query_type="gremlin",
            query_text="g.V().has('type', 'class')",
        )
        plan = router.create_query_plan(query, ["repo-001"])
        assert plan.query.query_id == "q-001"
        assert len(plan.target_shards) >= 1

    @pytest.mark.asyncio
    async def test_execute_federated_query(self, test_config):
        """Test executing federated query."""
        router = NeptuneShardRouter(config=test_config)
        query = GraphQuery(
            query_id="q-001",
            query_type="gremlin",
            query_text="g.V().limit(10)",
        )
        result = await router.execute_federated_query(query, ["repo-001"])
        assert result.success is True

    def test_get_shard_stats(self, test_config):
        """Test getting shard stats."""
        router = NeptuneShardRouter(config=test_config)
        stats = router.get_shard_stats()
        assert "num_shards" in stats
        assert "shards" in stats


class TestPolyglotDependencyGraph:
    """Tests for PolyglotDependencyGraph."""

    def test_initialize(self, test_config):
        """Test graph initialization."""
        graph = PolyglotDependencyGraph(test_config)
        assert graph is not None

    def test_singleton(self, test_config):
        """Test singleton pattern."""
        graph1 = get_dependency_graph()
        graph2 = get_dependency_graph()
        assert graph1 is graph2

    def test_reset_singleton(self, test_config):
        """Test singleton reset."""
        graph1 = get_dependency_graph()
        reset_dependency_graph()
        graph2 = get_dependency_graph()
        assert graph1 is not graph2

    @pytest.mark.asyncio
    async def test_add_entity(self, graph, sample_entity):
        """Test adding entity."""
        entity_id = await graph.add_entity(sample_entity)
        assert entity_id == sample_entity.id

    @pytest.mark.asyncio
    async def test_add_duplicate_entity(self, graph, sample_entity):
        """Test adding duplicate entity fails."""
        await graph.add_entity(sample_entity)
        with pytest.raises(DuplicateEntityError):
            await graph.add_entity(sample_entity)

    @pytest.mark.asyncio
    async def test_get_entity(self, graph, sample_entity):
        """Test getting entity."""
        await graph.add_entity(sample_entity)
        retrieved = await graph.get_entity(sample_entity.id)
        assert retrieved is not None
        assert retrieved.name == sample_entity.name

    @pytest.mark.asyncio
    async def test_get_nonexistent_entity(self, graph):
        """Test getting non-existent entity."""
        retrieved = await graph.get_entity("nonexistent")
        assert retrieved is None

    @pytest.mark.asyncio
    async def test_add_relationship(self, graph, sample_entities):
        """Test adding relationship."""
        for entity in sample_entities[:2]:
            await graph.add_entity(entity)

        relationship = CodeRelationship(
            id="rel-001",
            source_id=sample_entities[0].id,
            target_id=sample_entities[1].id,
            type=RelationType.IMPORTS,
        )

        rel_id = await graph.add_relationship(relationship)
        assert rel_id == "rel-001"

    @pytest.mark.asyncio
    async def test_add_relationship_invalid_source(self, graph, sample_entity):
        """Test adding relationship with invalid source."""
        await graph.add_entity(sample_entity)

        relationship = CodeRelationship(
            id="rel-001",
            source_id="nonexistent",
            target_id=sample_entity.id,
            type=RelationType.IMPORTS,
        )

        with pytest.raises(EntityNotFoundError):
            await graph.add_relationship(relationship)

    @pytest.mark.asyncio
    async def test_index_repository(self, graph, test_config):
        """Test indexing repository."""
        result = await graph.index_repository(
            repository_id="repo-001",
            repository_path="/path/to/repo",
            languages=[Language.PYTHON],
        )

        assert result.repository_id == "repo-001"
        assert result.status == IndexStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_update_incremental(self, graph, test_config):
        """Test incremental update."""
        # First index the repo
        await graph.index_repository(
            repository_id="repo-001",
            repository_path="/path/to/repo",
        )

        result = await graph.update_incremental(
            repository_id="repo-001",
            commit_sha="abc123",
            changed_files=["src/main.py", "src/utils.py"],
        )

        assert result.repository_id == "repo-001"
        assert result.files_updated == 2

    @pytest.mark.asyncio
    async def test_update_unindexed_repository(self, graph):
        """Test updating unindexed repository."""
        with pytest.raises(RepositoryNotIndexedError):
            await graph.update_incremental(
                repository_id="nonexistent",
                commit_sha="abc123",
                changed_files=["file.py"],
            )

    @pytest.mark.asyncio
    async def test_get_dependencies(self, graph, sample_entities):
        """Test getting dependencies."""
        for entity in sample_entities[:2]:
            await graph.add_entity(entity)

        relationship = CodeRelationship(
            id="rel-001",
            source_id=sample_entities[0].id,
            target_id=sample_entities[1].id,
            type=RelationType.IMPORTS,
        )
        await graph.add_relationship(relationship)

        deps = await graph.get_dependencies(sample_entities[0].id)
        assert len(deps) >= 1

    @pytest.mark.asyncio
    async def test_get_dependents(self, graph, sample_entities):
        """Test getting dependents."""
        for entity in sample_entities[:2]:
            await graph.add_entity(entity)

        relationship = CodeRelationship(
            id="rel-001",
            source_id=sample_entities[0].id,
            target_id=sample_entities[1].id,
            type=RelationType.IMPORTS,
        )
        await graph.add_relationship(relationship)

        dependents = await graph.get_dependents(sample_entities[1].id)
        assert len(dependents) >= 1
        assert dependents[0].id == sample_entities[0].id

    @pytest.mark.asyncio
    async def test_analyze_impact(self, graph, sample_entities):
        """Test impact analysis."""
        # Index repo first
        await graph.index_repository(
            repository_id="repo-001",
            repository_path="/path/to/repo",
        )

        # Add entities
        for entity in sample_entities:
            entity.repository_id = "repo-001"
            await graph.add_entity(entity)

        # Add relationship
        relationship = CodeRelationship(
            id="rel-001",
            source_id=sample_entities[0].id,
            target_id=sample_entities[1].id,
            type=RelationType.IMPORTS,
        )
        await graph.add_relationship(relationship)

        analysis = await graph.analyze_impact(
            repository_id="repo-001",
            changed_entity_ids=[sample_entities[1].id],
        )

        assert analysis.repository_id == "repo-001"
        assert analysis.changed_entity.id == sample_entities[1].id

    @pytest.mark.asyncio
    async def test_query(self, graph, test_config):
        """Test graph query."""
        query = GraphQuery(
            query_id="q-001",
            query_type="gremlin",
            query_text="g.V().limit(10)",
        )
        result = await graph.query(query)
        assert result.success is True

    def test_get_repository(self, graph):
        """Test getting non-existent repository."""
        repo = graph.get_repository("nonexistent")
        assert repo is None

    def test_list_repositories(self, graph):
        """Test listing repositories."""
        repos = graph.list_repositories()
        assert isinstance(repos, list)
