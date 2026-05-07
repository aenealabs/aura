"""
Project Aura - Polyglot Dependency Graph Service

Unified cross-language dependency graph supporting Go, Java,
Python, TypeScript, C++, Rust with billion-node scalability
via Neptune sharding.

Based on ADR-079: Scale & AI Model Security

Services:
- PolyglotDependencyGraph: Cross-language dependency tracking
- NeptuneShardRouter: Hash-based Neptune sharding

Key Features:
- 12+ language support
- Billion-node scalability
- Real-time incremental updates
- Impact analysis
- Vulnerability propagation tracking
"""

# Configuration
from .config import (
    CacheConfig,
    ImpactAnalysisConfig,
    IndexingConfig,
    MetricsConfig,
    NeptuneConfig,
    PolyglotConfig,
    ShardingConfig,
    VulnerabilityConfig,
    get_polyglot_config,
    reset_polyglot_config,
    set_polyglot_config,
)

# Contracts
from .contracts import (
    CodeEntity,
    CodeRelationship,
    CrossLanguageDependency,
    DependencyDiff,
    DependencyNode,
    DependencyType,
    Ecosystem,
    EntityType,
    FederatedQueryPlan,
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
    ShardConfig,
    VulnerabilityPropagation,
    VulnerabilityStatus,
)
from .dependency_graph import (
    PolyglotDependencyGraph,
    get_dependency_graph,
    reset_dependency_graph,
)

# Exceptions
from .exceptions import (
    AnalysisDepthExceededError,
    AnalysisTimeoutError,
    CyclicDependencyError,
    DependencyError,
    DependencyResolutionError,
    DuplicateEntityError,
    EntityError,
    EntityNotFoundError,
    FederatedQueryError,
    FileTooLargeError,
    ImpactAnalysisError,
    IndexingError,
    IndexingFailedError,
    IndexingInProgressError,
    InvalidEntityError,
    NeptuneCapacityError,
    NeptuneConnectionError,
    NeptuneError,
    NeptuneQueryError,
    NeptuneThrottlingError,
    NeptuneTimeoutError,
    PackageNotFoundError,
    ParseError,
    PolyglotError,
    RepositoryNotIndexedError,
    ShardError,
    ShardNotFoundError,
    ShardRoutingError,
    ShardUnavailableError,
    TooManyAffectedEntitiesError,
    TooManyFilesError,
    UnsupportedLanguageError,
    VersionNotFoundError,
    VulnerabilityDatabaseError,
    VulnerabilityError,
    VulnerabilityNotFoundError,
)

# Services
from .neptune_sharding import NeptuneShardRouter, get_shard_router, reset_shard_router

__all__ = [
    # Contracts
    "CodeEntity",
    "CodeRelationship",
    "CrossLanguageDependency",
    "DependencyDiff",
    "DependencyNode",
    "DependencyType",
    "Ecosystem",
    "EntityType",
    "FederatedQueryPlan",
    "GraphQuery",
    "GraphQueryResult",
    "ImpactAnalysis",
    "IncrementalUpdate",
    "IndexingResult",
    "IndexStatus",
    "Language",
    "LanguageStats",
    "PackageVulnerability",
    "RelationType",
    "RepositoryGraph",
    "ShardConfig",
    "VulnerabilityPropagation",
    "VulnerabilityStatus",
    # Configuration
    "CacheConfig",
    "ImpactAnalysisConfig",
    "IndexingConfig",
    "MetricsConfig",
    "NeptuneConfig",
    "PolyglotConfig",
    "ShardingConfig",
    "VulnerabilityConfig",
    "get_polyglot_config",
    "reset_polyglot_config",
    "set_polyglot_config",
    # Exceptions
    "AnalysisDepthExceededError",
    "AnalysisTimeoutError",
    "CyclicDependencyError",
    "DependencyError",
    "DependencyResolutionError",
    "DuplicateEntityError",
    "EntityError",
    "EntityNotFoundError",
    "FederatedQueryError",
    "FileTooLargeError",
    "ImpactAnalysisError",
    "IndexingError",
    "IndexingFailedError",
    "IndexingInProgressError",
    "InvalidEntityError",
    "NeptuneCapacityError",
    "NeptuneConnectionError",
    "NeptuneError",
    "NeptuneQueryError",
    "NeptuneThrottlingError",
    "NeptuneTimeoutError",
    "PackageNotFoundError",
    "ParseError",
    "PolyglotError",
    "RepositoryNotIndexedError",
    "ShardError",
    "ShardNotFoundError",
    "ShardRoutingError",
    "ShardUnavailableError",
    "TooManyAffectedEntitiesError",
    "TooManyFilesError",
    "UnsupportedLanguageError",
    "VersionNotFoundError",
    "VulnerabilityDatabaseError",
    "VulnerabilityError",
    "VulnerabilityNotFoundError",
    # Services
    "NeptuneShardRouter",
    "get_shard_router",
    "reset_shard_router",
    "PolyglotDependencyGraph",
    "get_dependency_graph",
    "reset_dependency_graph",
]
