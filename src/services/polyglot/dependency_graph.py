"""
Project Aura - Polyglot Dependency Graph

Unified cross-language dependency graph supporting Go, Java,
Python, TypeScript, C++, Rust with billion-node scalability.

Based on ADR-079: Scale & AI Model Security
"""

import os
import uuid
from collections import defaultdict
from datetime import datetime, timezone
from typing import Optional

from .config import PolyglotConfig, get_polyglot_config
from .contracts import (
    CodeEntity,
    CodeRelationship,
    CrossLanguageDependency,
    DependencyNode,
    DependencyType,
    Ecosystem,
    EntityType,
    GraphQuery,
    GraphQueryResult,
    ImpactAnalysis,
    IncrementalUpdate,
    IndexingResult,
    IndexStatus,
    Language,
    LanguageStats,
    PackageVulnerability,
    RelationType,
    RepositoryGraph,
    VulnerabilityPropagation,
)
from .exceptions import (
    DuplicateEntityError,
    EntityNotFoundError,
    IndexingFailedError,
    IndexingInProgressError,
    RepositoryNotIndexedError,
    TooManyAffectedEntitiesError,
)
from .neptune_sharding import get_shard_router

# Language file extensions
LANGUAGE_EXTENSIONS = {
    ".py": Language.PYTHON,
    ".js": Language.JAVASCRIPT,
    ".jsx": Language.JAVASCRIPT,
    ".ts": Language.TYPESCRIPT,
    ".tsx": Language.TYPESCRIPT,
    ".go": Language.GO,
    ".java": Language.JAVA,
    ".kt": Language.KOTLIN,
    ".rs": Language.RUST,
    ".cpp": Language.CPP,
    ".cc": Language.CPP,
    ".c": Language.C,
    ".h": Language.C,
    ".hpp": Language.CPP,
    ".cs": Language.CSHARP,
    ".rb": Language.RUBY,
    ".php": Language.PHP,
    ".swift": Language.SWIFT,
    ".scala": Language.SCALA,
}

# Language to ecosystem mapping
LANGUAGE_ECOSYSTEMS = {
    Language.PYTHON: Ecosystem.PYPI,
    Language.JAVASCRIPT: Ecosystem.NPM,
    Language.TYPESCRIPT: Ecosystem.NPM,
    Language.GO: Ecosystem.GO,
    Language.JAVA: Ecosystem.MAVEN,
    Language.KOTLIN: Ecosystem.MAVEN,
    Language.RUST: Ecosystem.CARGO,
    Language.CSHARP: Ecosystem.NUGET,
    Language.RUBY: Ecosystem.RUBYGEMS,
    Language.PHP: Ecosystem.PACKAGIST,
}


class PolyglotDependencyGraph:
    """
    Unified dependency graph across languages.

    Features:
    - Cross-language dependency tracking
    - Billion-node scalability (Neptune sharding)
    - Real-time incremental updates
    - Impact analysis
    - Vulnerability propagation tracking
    """

    def __init__(self, config: Optional[PolyglotConfig] = None):
        """Initialize dependency graph."""
        self._config = config or get_polyglot_config()
        self._shard_router = get_shard_router()

        # In-memory storage for testing
        self._entities: dict[str, CodeEntity] = {}
        self._relationships: dict[str, CodeRelationship] = {}
        self._repositories: dict[str, RepositoryGraph] = {}
        self._packages: dict[str, DependencyNode] = {}
        self._vulnerabilities: dict[str, PackageVulnerability] = {}
        self._indexing_status: dict[str, IndexStatus] = {}

        # Adjacency indices for O(1) lookup by source/target
        self._outgoing: dict[str, list] = defaultdict(
            list
        )  # source_id -> [relationships]
        self._incoming: dict[str, list] = defaultdict(
            list
        )  # target_id -> [relationships]

    async def index_repository(
        self,
        repository_id: str,
        repository_path: str,
        languages: Optional[list[Language]] = None,
    ) -> IndexingResult:
        """Index repository into dependency graph."""
        if repository_id in self._indexing_status:
            if self._indexing_status[repository_id] == IndexStatus.INDEXING:
                raise IndexingInProgressError(repository_id)

        self._indexing_status[repository_id] = IndexStatus.INDEXING
        index_id = self._generate_id("index")
        started_at = datetime.now(timezone.utc)

        try:
            # Detect languages if not specified
            detected_languages = languages or []
            total_files = 0
            total_entities = 0
            total_relationships = 0
            errors = []

            # In a real implementation, this would walk the repository
            # For now, simulate indexing

            # Create repository graph entry
            self._repositories[repository_id] = RepositoryGraph(
                repository_id=repository_id,
                name=repository_id,
                languages=[
                    LanguageStats(language=lang, file_count=0)
                    for lang in detected_languages
                ],
                total_entities=total_entities,
                total_relationships=total_relationships,
                index_status=IndexStatus.COMPLETED,
                last_indexed_at=datetime.now(timezone.utc),
            )

            self._indexing_status[repository_id] = IndexStatus.COMPLETED

            return IndexingResult(
                index_id=index_id,
                repository_id=repository_id,
                status=IndexStatus.COMPLETED,
                languages_detected=detected_languages,
                total_files=total_files,
                total_entities=total_entities,
                total_relationships=total_relationships,
                errors=errors,
                duration_seconds=(
                    datetime.now(timezone.utc) - started_at
                ).total_seconds(),
                started_at=started_at,
                completed_at=datetime.now(timezone.utc),
            )

        except Exception as e:
            self._indexing_status[repository_id] = IndexStatus.FAILED
            raise IndexingFailedError(repository_id, str(e))

    async def update_incremental(
        self,
        repository_id: str,
        commit_sha: str,
        changed_files: list[str],
    ) -> IncrementalUpdate:
        """Incrementally update graph with changes."""
        if repository_id not in self._repositories:
            raise RepositoryNotIndexedError(repository_id)

        update_id = self._generate_id("update")
        start_time = datetime.now(timezone.utc)

        entities_added = 0
        entities_removed = 0
        entities_modified = 0
        relationships_added = 0
        relationships_removed = 0

        # Process changed files
        for file_path in changed_files:
            # Detect language
            language = self._detect_language(file_path)
            if not language:
                continue

            # In a real implementation, would parse file and update graph
            # For simulation, count as modified
            entities_modified += 1

        duration_ms = int(
            (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
        )

        return IncrementalUpdate(
            update_id=update_id,
            repository_id=repository_id,
            commit_sha=commit_sha,
            files_updated=len(changed_files),
            entities_added=entities_added,
            entities_removed=entities_removed,
            entities_modified=entities_modified,
            relationships_added=relationships_added,
            relationships_removed=relationships_removed,
            duration_ms=duration_ms,
        )

    async def add_entity(self, entity: CodeEntity) -> str:
        """Add entity to graph."""
        if entity.id in self._entities:
            raise DuplicateEntityError(entity.id, entity.qualified_name)

        self._entities[entity.id] = entity
        return entity.id

    async def get_entity(self, entity_id: str) -> Optional[CodeEntity]:
        """Get entity by ID."""
        return self._entities.get(entity_id)

    async def add_relationship(self, relationship: CodeRelationship) -> str:
        """Add relationship to graph."""
        # Validate source and target exist
        if relationship.source_id not in self._entities:
            raise EntityNotFoundError(relationship.source_id)
        if relationship.target_id not in self._entities:
            raise EntityNotFoundError(relationship.target_id)

        self._relationships[relationship.id] = relationship
        self._outgoing[relationship.source_id].append(relationship)
        self._incoming[relationship.target_id].append(relationship)
        return relationship.id

    async def get_dependencies(
        self,
        entity_id: str,
        depth: int = -1,
        include_transitive: bool = True,
    ) -> list[DependencyNode]:
        """Get dependency tree for entity."""
        if entity_id not in self._entities:
            raise EntityNotFoundError(entity_id)

        dependencies = []
        visited = set()
        max_depth = depth if depth > 0 else self._config.impact_analysis.max_depth

        await self._collect_dependencies(
            entity_id, dependencies, visited, 0, max_depth, include_transitive
        )

        return dependencies

    async def _collect_dependencies(
        self,
        entity_id: str,
        dependencies: list[DependencyNode],
        visited: set[str],
        current_depth: int,
        max_depth: int,
        include_transitive: bool,
    ) -> None:
        """Recursively collect dependencies."""
        if entity_id in visited or current_depth >= max_depth:
            return

        visited.add(entity_id)

        # Find relationships where this entity is the source
        for rel in self._outgoing.get(entity_id, []):
            if rel.type == RelationType.IMPORTS:
                target = self._entities.get(rel.target_id)
                if target:
                    dep_node = DependencyNode(
                        package_name=target.qualified_name,
                        version="*",
                        language=target.language,
                        ecosystem=LANGUAGE_ECOSYSTEMS.get(
                            target.language, Ecosystem.NPM
                        ),
                        dep_type=(
                            DependencyType.DIRECT
                            if current_depth == 0
                            else DependencyType.TRANSITIVE
                        ),
                        depth=current_depth,
                    )
                    dependencies.append(dep_node)

                    if include_transitive:
                        await self._collect_dependencies(
                            rel.target_id,
                            dependencies,
                            visited,
                            current_depth + 1,
                            max_depth,
                            include_transitive,
                        )

    async def get_dependents(
        self,
        entity_id: str,
        depth: int = -1,
    ) -> list[CodeEntity]:
        """Get entities that depend on this one."""
        if entity_id not in self._entities:
            raise EntityNotFoundError(entity_id)

        dependents = []
        visited = set()
        max_depth = depth if depth > 0 else self._config.impact_analysis.max_depth

        await self._collect_dependents(entity_id, dependents, visited, 0, max_depth)

        return dependents

    async def _collect_dependents(
        self,
        entity_id: str,
        dependents: list[CodeEntity],
        visited: set[str],
        current_depth: int,
        max_depth: int,
    ) -> None:
        """Recursively collect dependents."""
        if entity_id in visited or current_depth >= max_depth:
            return

        visited.add(entity_id)

        # Find relationships where this entity is the target
        for rel in self._incoming.get(entity_id, []):
            source = self._entities.get(rel.source_id)
            if source and source.id not in visited:
                dependents.append(source)
                await self._collect_dependents(
                    rel.source_id,
                    dependents,
                    visited,
                    current_depth + 1,
                    max_depth,
                )

    async def analyze_impact(
        self,
        repository_id: str,
        changed_entity_ids: list[str],
    ) -> ImpactAnalysis:
        """Analyze impact of changes."""
        if repository_id not in self._repositories:
            raise RepositoryNotIndexedError(repository_id)

        analysis_id = self._generate_id("impact")

        # Get first changed entity
        if not changed_entity_ids:
            raise EntityNotFoundError("No entities specified")

        changed_entity = self._entities.get(changed_entity_ids[0])
        if not changed_entity:
            raise EntityNotFoundError(changed_entity_ids[0])

        # Get direct and transitive dependents
        directly_affected = []
        transitively_affected = []
        affected_tests = []

        for entity_id in changed_entity_ids:
            dependents = await self.get_dependents(entity_id, depth=1)
            directly_affected.extend(dependents)

            all_dependents = await self.get_dependents(
                entity_id, depth=self._config.impact_analysis.max_depth
            )
            transitively_affected.extend(
                [d for d in all_dependents if d not in directly_affected]
            )

            # Find affected tests
            for dep in all_dependents:
                if "test" in dep.file_path.lower():
                    affected_tests.append(dep.file_path)

        # Check limits
        total_affected = len(directly_affected) + len(transitively_affected)
        if total_affected > self._config.impact_analysis.max_affected_entities:
            raise TooManyAffectedEntitiesError(
                analysis_id,
                total_affected,
                self._config.impact_analysis.max_affected_entities,
            )

        # Calculate risk score
        risk_score = self._calculate_risk_score(
            len(directly_affected),
            len(transitively_affected),
            len(affected_tests),
        )

        return ImpactAnalysis(
            analysis_id=analysis_id,
            repository_id=repository_id,
            changed_entity=changed_entity,
            directly_affected=directly_affected,
            transitively_affected=transitively_affected,
            affected_tests=affected_tests,
            risk_score=risk_score,
            analysis_depth=self._config.impact_analysis.max_depth,
        )

    def _calculate_risk_score(
        self,
        direct_count: int,
        transitive_count: int,
        test_count: int,
    ) -> float:
        """Calculate risk score based on impact."""
        # Simple risk calculation
        score = (
            direct_count * 10.0 + transitive_count * 2.0 + (100.0 - test_count * 5.0)
        )
        return min(100.0, max(0.0, score))

    async def find_vulnerability_propagation(
        self,
        vulnerability: PackageVulnerability,
    ) -> VulnerabilityPropagation:
        """Find all code affected by vulnerable package."""
        propagation_id = self._generate_id("vuln-prop")
        affected_entities = []
        propagation_paths = []

        # Find entities that use the vulnerable package
        for entity in self._entities.values():
            # Check if entity imports the vulnerable package
            for rel in self._outgoing.get(entity.id, []):
                target = self._entities.get(rel.target_id)
                if target and vulnerability.package_name in target.qualified_name:
                    affected_entities.append(entity)
                    propagation_paths.append(
                        [entity.qualified_name, target.qualified_name]
                    )

        # Count affected files and functions
        affected_files = {e.file_path for e in affected_entities}
        affected_functions = [
            e for e in affected_entities if e.type == EntityType.FUNCTION
        ]

        # Calculate risk score
        risk_score = len(affected_entities) * 10.0
        if vulnerability.cvss_score:
            risk_score *= vulnerability.cvss_score / 10.0

        return VulnerabilityPropagation(
            propagation_id=propagation_id,
            vulnerability=vulnerability,
            affected_entities=affected_entities,
            propagation_paths=propagation_paths,
            total_affected_files=len(affected_files),
            total_affected_functions=len(affected_functions),
            risk_score=min(100.0, risk_score),
        )

    async def get_cross_language_dependencies(
        self,
        repository_id: str,
    ) -> list[CrossLanguageDependency]:
        """Get dependencies that cross language boundaries."""
        if repository_id not in self._repositories:
            raise RepositoryNotIndexedError(repository_id)

        cross_lang_deps = []

        for rel in self._relationships.values():
            if rel.is_cross_language:
                source = self._entities.get(rel.source_id)
                target = self._entities.get(rel.target_id)

                if source and target and source.language != target.language:
                    cross_lang_deps.append(
                        CrossLanguageDependency(
                            dependency_id=self._generate_id("xdep"),
                            source_entity=source,
                            target_entity=target,
                            source_language=source.language,
                            target_language=target.language,
                            binding_type=rel.metadata.get("binding_type", "unknown"),
                        )
                    )

        return cross_lang_deps

    async def query(self, query: GraphQuery) -> GraphQueryResult:
        """Execute a graph query."""
        return await self._shard_router.execute_federated_query(query)

    def get_repository(self, repository_id: str) -> Optional[RepositoryGraph]:
        """Get repository graph."""
        return self._repositories.get(repository_id)

    def list_repositories(self) -> list[RepositoryGraph]:
        """List all repositories."""
        return list(self._repositories.values())

    def _detect_language(self, file_path: str) -> Optional[Language]:
        """Detect language from file path."""
        ext = os.path.splitext(file_path)[1].lower()
        return LANGUAGE_EXTENSIONS.get(ext)

    def _generate_id(self, prefix: str) -> str:
        """Generate unique ID."""
        return f"{prefix}-{uuid.uuid4().hex[:12]}"


# Singleton pattern
_dependency_graph: Optional[PolyglotDependencyGraph] = None


def get_dependency_graph() -> PolyglotDependencyGraph:
    """Get singleton dependency graph."""
    global _dependency_graph
    if _dependency_graph is None:
        _dependency_graph = PolyglotDependencyGraph()
    return _dependency_graph


def reset_dependency_graph() -> None:
    """Reset singleton dependency graph."""
    global _dependency_graph
    _dependency_graph = None
